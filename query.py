"""
Cannabis Law Assistant - 查询脚本
支持中英文提问，自动翻译 → 混合检索（向量 + BM25 + RRF）→ 中文回答

用法：
  python query.py                  # 交互模式（推荐）
  python query.py "你的问题"        # 单次查询
"""

import os
import pickle
import sys
from datetime import date

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings

# ─────────────────────────────────────────────
# 环境变量
# ─────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME    = os.getenv("CHROMA_COLLECTION_NAME", "cannabis_law_nyc")
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
BM25_INDEX_PATH    = "./bm25_index.pkl"

TODAY = date.today().isoformat()  # 用于时效性警告判断


# ─────────────────────────────────────────────
# 初始化客户端（全局复用）
# ─────────────────────────────────────────────
def init_clients():
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY 未设置，请在 .env 文件中填入真实 API Key。")

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    embeddings    = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    collection    = chroma_client.get_collection(COLLECTION_NAME)

    with open(BM25_INDEX_PATH, "rb") as f:
        index_data = pickle.load(f)

    return openai_client, embeddings, collection, index_data


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def is_chinese(text: str) -> bool:
    """简单判断文本是否含有中文字符。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def translate_to_english(client: OpenAI, text: str) -> str:
    """将中文查询翻译为英文，用于检索增强。"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a legal translation assistant. "
                    "Translate the user's Chinese question about cannabis law into clear, "
                    "concise English. Output only the translated text, no explanations."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def rrf_fusion(vec_ids: list[str], bm25_ids: list[str], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion 融合向量检索与 BM25 排名。"""
    scores: dict[str, float] = {}
    for rank, cid in enumerate(vec_ids):
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    for rank, cid in enumerate(bm25_ids):
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def hybrid_search(
    query_en: str,
    embeddings: OpenAIEmbeddings,
    collection,
    index_data: dict,
    top_k: int = 3,
) -> list[dict]:
    """
    混合检索：向量检索 Top-10 + BM25 Top-10 → RRF 融合 → 返回 Top-k chunk。
    """
    bm25      = index_data["bm25"]
    chunk_ids = index_data["chunk_ids"]
    texts     = index_data["texts"]
    metadatas = index_data["metadatas"]

    # 向量检索
    query_vec   = embeddings.embed_query(query_en)
    vec_results = collection.query(
        query_embeddings=[query_vec],
        n_results=10,
        include=["documents", "metadatas"],
    )
    vec_ids = vec_results["ids"][0]

    # BM25 检索
    tokenized    = query_en.lower().split()
    bm25_scores  = bm25.get_scores(tokenized)
    top10_idx    = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:10]
    bm25_ids     = [chunk_ids[i] for i in top10_idx]

    # RRF 融合
    fused_ids = rrf_fusion(vec_ids, bm25_ids)[:top_k]

    # 取回完整 chunk 内容
    id_to_idx = {cid: i for i, cid in enumerate(chunk_ids)}
    results = []
    for cid in fused_ids:
        idx = id_to_idx.get(cid)
        if idx is None:
            continue
        results.append({
            "chunk_id":   cid,
            "text":       texts[idx],
            "metadata":   metadatas[idx],
        })
    return results


def build_context(chunks: list[dict]) -> tuple[str, list[str]]:
    """
    将检索到的 chunk 拼成 LLM context 字符串。
    同时收集时效性警告。
    """
    context_parts = []
    warnings      = []

    for i, chunk in enumerate(chunks, 1):
        meta  = chunk["metadata"]
        text  = chunk["text"]
        label = (
            f"[来源 {i}] 文件：{meta.get('file_name', '')} | "
            f"领域：{meta.get('domain', '')} | "
            f"章节：{meta.get('section_title', '')[:60]}"
        )
        context_parts.append(f"{label}\n{text}")

        if meta.get("time_sensitive"):
            note     = meta.get("deadline_note", "")
            warnings.append(f"⚠️  时效警告：{note}（今天：{TODAY}）")

    return "\n\n---\n\n".join(context_parts), warnings


def generate_answer(
    client: OpenAI,
    question_zh: str,
    question_en: str,
    context: str,
    warnings: list[str],
) -> str:
    """调用 GPT-4o-mini 生成中文法律回答。"""
    warning_block = "\n".join(warnings) if warnings else ""
    warning_text  = f"\n\n{warning_block}\n" if warning_block else ""

    system_prompt = (
        "你是一位专业的纽约州大麻法律顾问，擅长解释纽约州及纽约市大麻相关法规。\n"
        "请根据以下法规原文内容，用简洁、准确的中文回答用户问题。\n"
        "回答要求：\n"
        "1. 直接回答问题，引用具体法规条款或章节编号\n"
        "2. 如有不确定之处，说明需进一步查阅原文\n"
        "3. 如果检索内容与问题不相关，直接告知用户\n"
        "4. 不要编造法规内容"
    )

    user_prompt = (
        f"用户问题（中文）：{question_zh}\n"
        f"英文检索版本：{question_en}\n"
        f"{warning_text}"
        f"\n相关法规原文：\n{context}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────
# 主查询函数
# ─────────────────────────────────────────────
def ask(question: str, openai_client, embeddings, collection, index_data) -> str:
    """
    完整查询流程：
    1. 检测语言，中文则翻译为英文
    2. 混合检索 Top-3
    3. 构建 context + 时效性警告
    4. 生成中文回答
    """
    # 1. 语言检测与翻译
    if is_chinese(question):
        print(f"  [翻译] 正在将问题翻译为英文...")
        question_en = translate_to_english(openai_client, question)
        print(f"  [翻译] {question_en}")
    else:
        question_en = question

    # 2. 混合检索
    print(f"  [检索] 向量 + BM25 混合检索中...")
    chunks = hybrid_search(question_en, embeddings, collection, index_data)

    if not chunks:
        return "未找到相关法规内容，请尝试换一种表述方式。"

    # 3. 构建 context
    context, warnings = build_context(chunks)

    # 打印来源摘要
    print(f"  [来源] 检索到 {len(chunks)} 个相关 chunk：")
    for c in chunks:
        meta = c["metadata"]
        ts   = " ⚠️时效" if meta.get("time_sensitive") else ""
        print(f"         - {meta.get('file_name')} | {meta.get('domain')} | {meta.get('section_title', '')[:50]}{ts}")

    # 4. 生成回答
    print(f"  [生成] 正在生成回答...")
    answer = generate_answer(openai_client, question, question_en, context, warnings)
    return answer


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
def main():
    print("Cannabis Law Assistant 初始化中...")
    openai_client, embeddings, collection, index_data = init_clients()
    print("✅ 就绪！输入问题开始查询（输入 'quit' 或 'q' 退出）\n")

    # 单次查询模式（命令行传参）
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"问题：{question}")
        print("-" * 60)
        answer = ask(question, openai_client, embeddings, collection, index_data)
        print(f"\n回答：\n{answer}")
        return

    # 交互模式
    while True:
        try:
            question = input("问题：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if not question:
            continue
        if question.lower() in ("quit", "q", "exit", "退出"):
            print("退出。")
            break

        print("-" * 60)
        answer = ask(question, openai_client, embeddings, collection, index_data)
        print(f"\n回答：\n{answer}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
