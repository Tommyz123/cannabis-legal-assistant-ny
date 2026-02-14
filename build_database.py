"""
Cannabis Law Assistant - RAG 向量数据库构建脚本
方案：ChromaDB + LangChain + OpenAI Embedding + BM25 混合检索索引

运行前准备：
  1. python3 -m venv venv && source venv/bin/activate
  2. pip install -r requirements.txt
  3. cp .env.example .env  # 填入真实 OPENAI_API_KEY
  4. python build_database.py
"""

import os
import pickle
import re
import sys

# Windows terminal UTF-8 fix
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

import chromadb
import tiktoken
from dotenv import load_dotenv
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi

# ─────────────────────────────────────────────
# 环境变量
# ─────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
CHROMA_PERSIST_DIR  = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME     = os.getenv("CHROMA_COLLECTION_NAME", "cannabis_law_nyc")
EMBEDDING_MODEL     = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
KNOWLEDGE_DIR       = os.getenv("KNOWLEDGE_DIR", ".")

# BM25 索引持久化路径
BM25_INDEX_PATH = "./bm25_index.pkl"

# ─────────────────────────────────────────────
# 14 个知识文件的元数据定义
# ─────────────────────────────────────────────
DOCUMENT_METADATA = {
    "01_General_Regs.md": {
        "doc_id":       "01_general_regs",
        "domain":       "general",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, compliance_officer",
        "keywords":     "license, OCM, conditional adult-use, CAURD, dispensary",
    },
    "02_Packaging_Labeling.md": {
        "doc_id":       "02_packaging_labeling",
        "domain":       "packaging",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, product_manager",
        "keywords":     "label, child-resistant, THC symbol, warning, packaging",
    },
    "03_Security_Storage.md": {
        "doc_id":       "03_security_storage",
        "domain":       "security",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, security_manager",
        "keywords":     "surveillance, vault, alarm, storage, restricted access",
    },
    "04_Retail_Operations.md": {
        "doc_id":       "04_retail_operations",
        "domain":       "retail",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, store_manager",
        "keywords":     "POS, inventory, METRC, track-and-trace, adult-use",
    },
    "05_Official_Guidance.md": {
        "doc_id":       "05_official_guidance",
        "domain":       "guidance",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, compliance_officer, attorney",
        "keywords":     "OCM guidance, FAQ, policy, proximity, buffer zone",
    },
    "06_FDNY_Fire_Code.md": {
        "doc_id":       "06_fdny_fire_code",
        "domain":       "fire_safety",
        "jurisdiction": "New York City",
        "audience":     "dispensary_owner, facility_manager",
        "keywords":     "FDNY, fire code, storage limit, permit, CO2",
    },
    "07_Tax_Guidance.md": {
        "doc_id":       "07_tax_guidance",
        "domain":       "tax",
        "jurisdiction": "Federal, New York State",
        "audience":     "dispensary_owner, accountant, attorney",
        "keywords":     "280E, COGS, excise tax, sales tax, quarterly filing",
    },
    "08_Labor_Rights.md": {
        "doc_id":       "08_labor_rights",
        "domain":       "labor",
        "jurisdiction": "Federal, New York State",
        "audience":     "dispensary_owner, HR_manager",
        "keywords":     "minimum wage, WARN Act, cannabis labor peace, union",
    },
    "09_Marketing_Advertising.md": {
        "doc_id":       "09_marketing_advertising",
        "domain":       "marketing",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, marketing_manager",
        "keywords":     "advertising, social media, billboard, Part 129, 2026-02-24",
    },
    "09_Violations_Penalties.md": {
        "doc_id":       "09_violations_penalties",
        "domain":       "violations",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, compliance_officer, attorney",
        "keywords":     "penalty, fine, revocation, suspension, enforcement",
    },
    "10_Laboratory_Testing.md": {
        "doc_id":       "10_laboratory_testing",
        "domain":       "testing",
        "jurisdiction": "New York State",
        "audience":     "dispensary_owner, lab_manager, quality_control",
        "keywords":     "COA, cannabinoid, contaminant, batch testing, Part 130",
    },
    "12_NYC_DCWP_License.md": {
        "doc_id":       "12_nyc_dcwp_license",
        "domain":       "nyc_license",
        "jurisdiction": "New York City",
        "audience":     "dispensary_owner, compliance_officer",
        "keywords":     "DCWP, NYC license, local permit, zoning",
    },
    "15_Consumer_Protection.md": {
        "doc_id":       "15_consumer_protection",
        "domain":       "consumer_protection",
        "jurisdiction": "New York State, New York City",
        "audience":     "dispensary_owner, store_manager, consumer",
        "keywords":     "consumer right, return, recall, complaint, disclosure",
    },
    "COMPLIANCE_CHECKLIST.md": {
        "doc_id":       "compliance_checklist",
        "domain":       "compliance",
        "jurisdiction": "New York State, New York City",
        "audience":     "dispensary_owner, compliance_officer",
        "keywords":     "checklist, audit, inspection, renewal, compliance",
    },
    "16_Pre_Application_Guide.md": {
        "doc_id":       "16_pre_application_guide",
        "domain":       "pre_application",
        "jurisdiction": "New York State, New York City",
        "audience":     "dispensary_owner, applicant",
        "keywords":     "application, OCM, license, setup, business plan, community board, zoning, pre-opening, startup",
    },
}

# 时效性关键词映射：文件 doc_id → (关键词列表, deadline_note)
TIME_SENSITIVE_RULES = {
    "05_official_guidance": (
        ["proximity", "measurement", "buffer zone", "500 feet"],
        "Proximity measurement standard expires 2026-02-15",
    ),
    "09_marketing_advertising": (
        ["billboard", "transition", "outdoor advertising"],
        "Billboard transition deadline: 2026-02-24",
    ),
}

# 不向量化的文件
EXCLUDED_FILES = {
    "README.md",
    "PROJECT_SUMMARY.md",
    "CHANGELOG.md",
    "AI_Legal_Assistant_Database_Design_Report.md",
    "PROJECT_PLAN_RAG.md",
}


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """用 tiktoken 计算文本 token 数。"""
    enc = tiktoken.get_encoding(model)
    return len(enc.encode(text))


def is_time_sensitive(text: str, doc_id: str) -> tuple[bool, str]:
    """
    判断 chunk 是否含时效性内容。
    返回 (time_sensitive: bool, deadline_note: str)
    """
    rule = TIME_SENSITIVE_RULES.get(doc_id)
    if rule is None:
        return False, ""
    keywords, note = rule
    text_lower = text.lower()
    if any(kw.lower() in text_lower for kw in keywords):
        return True, note
    return False, ""


def load_and_split_file(file_path: str, meta: dict) -> list[dict]:
    """
    读取单个 Markdown 文件，按标题切分，二次切分过长块。
    返回 chunk 字典列表，每个字典包含 text 和 metadata。
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # ── 一次切分：按 ## 和 ### 标题 ──
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    header_chunks = header_splitter.split_text(content)

    # ── 二次切分：超过 600 tokens 的块再拆 ──
    secondary_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=250,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    result_chunks = []
    for hchunk in header_chunks:
        text = hchunk.page_content.strip()
        if not text or len(text) < 50:
            continue

        section_title = hchunk.metadata.get("h2") or hchunk.metadata.get("h3") or ""

        if count_tokens(text) > 600:
            sub_texts = secondary_splitter.split_text(text)
        else:
            sub_texts = [text]

        for sub_text in sub_texts:
            sub_text = sub_text.strip()
            if len(sub_text) < 50:
                continue
            result_chunks.append({
                "text": sub_text,
                "section_title": section_title,
            })

    # ── 附加元数据 ──
    doc_id = meta["doc_id"]
    final = []
    for idx, chunk in enumerate(result_chunks):
        text = chunk["text"]
        sensitive, note = is_time_sensitive(text, doc_id)
        token_cnt = count_tokens(text)

        chunk_meta = {
            "doc_id":         doc_id,
            "file_name":      os.path.basename(file_path),
            "domain":         meta["domain"],
            "jurisdiction":   meta["jurisdiction"],
            "audience":       meta["audience"],
            "keywords":       meta["keywords"],
            "section_title":  chunk["section_title"],
            "chunk_index":    idx,
            "chunk_id":       f"{doc_id}__{idx:03d}",
            "token_count":    token_cnt,
            "time_sensitive": sensitive,
        }
        if sensitive:
            chunk_meta["deadline_note"] = note

        final.append({"text": text, "metadata": chunk_meta})

    return final


# ─────────────────────────────────────────────
# 主构建函数
# ─────────────────────────────────────────────
def build_vector_database() -> list[dict]:
    """
    遍历所有知识文件 → 分块 → OpenAI Embedding → 存入 ChromaDB。
    返回所有 chunk 列表（供后续构建 BM25 索引）。
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY 未设置，请在 .env 文件中填入真实 API Key。")

    # ── ChromaDB 客户端（0.6.x 新 API）──
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # 集合已存在则先删除，支持重复运行
    existing = chroma_client.list_collections()  # 0.6.x 直接返回名称列表
    if COLLECTION_NAME in existing:
        print(f"[ChromaDB] 已存在集合 '{COLLECTION_NAME}'，先删除再重建...")
        chroma_client.delete_collection(COLLECTION_NAME)

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"[ChromaDB] 已创建集合 '{COLLECTION_NAME}'（cosine 距离）")

    # ── OpenAI Embedding ──
    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )

    # ── 收集所有 chunk ──
    all_chunks: list[dict] = []
    knowledge_dir = os.path.abspath(KNOWLEDGE_DIR)

    for file_name, meta in DOCUMENT_METADATA.items():
        if file_name in EXCLUDED_FILES:
            continue
        file_path = os.path.join(knowledge_dir, file_name)
        if not os.path.exists(file_path):
            print(f"  [警告] 文件不存在，跳过：{file_path}")
            continue

        chunks = load_and_split_file(file_path, meta)
        print(f"  {file_name}: {len(chunks)} 个 chunk")
        all_chunks.extend(chunks)

    print(f"\n[分块] 共 {len(all_chunks)} 个 chunk，开始生成向量并存入 ChromaDB...")

    # ── 批量存储（每批 50 块）──
    batch_size = 50
    total = len(all_chunks)
    for start in range(0, total, batch_size):
        batch = all_chunks[start: start + batch_size]
        texts     = [c["text"] for c in batch]
        metadatas = [c["metadata"] for c in batch]
        ids       = [c["metadata"]["chunk_id"] for c in batch]

        vectors = embeddings.embed_documents(texts)

        collection.add(
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )
        end = min(start + batch_size, total)
        print(f"  已存储 {end}/{total} 块...")

    print(f"\n[完成] ChromaDB 向量数据库构建完毕，持久化目录：{CHROMA_PERSIST_DIR}")
    return all_chunks


def build_bm25_index(all_chunks: list[dict]) -> None:
    """
    基于所有 chunk 文本构建 BM25Okapi 索引，持久化为 bm25_index.pkl。
    索引与 ChromaDB 共用同一份 chunk_id 列表，确保对齐。
    """
    print("\n[BM25] 开始构建关键词索引...")

    corpus_tokens = [chunk["text"].lower().split() for chunk in all_chunks]
    chunk_ids     = [chunk["metadata"]["chunk_id"] for chunk in all_chunks]

    bm25 = BM25Okapi(corpus_tokens)

    index_data = {
        "bm25":      bm25,
        "chunk_ids": chunk_ids,
        "texts":     [chunk["text"] for chunk in all_chunks],
        "metadatas": [chunk["metadata"] for chunk in all_chunks],
    }

    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(index_data, f)

    print(f"[BM25] 索引已保存至 {BM25_INDEX_PATH}（{len(chunk_ids)} 条记录）")


# ─────────────────────────────────────────────
# 测试查询（可选）
# ─────────────────────────────────────────────
def test_query() -> None:
    """
    简单验证：分别测试语义检索和精确条款检索。
    构建完成后取消注释 main() 中的调用即可运行。
    """
    print("\n" + "=" * 60)
    print("[测试] 开始混合检索验证")
    print("=" * 60)

    # ── 加载 ChromaDB ──
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    collection    = chroma_client.get_collection(COLLECTION_NAME)
    embeddings    = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )

    # ── 加载 BM25 索引 ──
    with open(BM25_INDEX_PATH, "rb") as f:
        index_data = pickle.load(f)
    bm25      = index_data["bm25"]
    chunk_ids = index_data["chunk_ids"]

    def rrf_fusion(vec_ids: list[str], bm25_ids: list[str], k: int = 60) -> list[str]:
        """Reciprocal Rank Fusion 融合两路排名。"""
        scores: dict[str, float] = {}
        for rank, cid in enumerate(vec_ids):
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
        for rank, cid in enumerate(bm25_ids):
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
        return sorted(scores, key=lambda x: scores[x], reverse=True)

    test_queries = [
        "What are the packaging requirements for cannabis products?",
        "Section 280E deductible expenses",
        "proximity measurement buffer zone",
    ]

    for query in test_queries:
        print(f"\n查询：{query}")
        print("-" * 50)

        # 向量检索 Top-10
        query_vec = embeddings.embed_query(query)
        vec_results = collection.query(
            query_embeddings=[query_vec],
            n_results=10,
            include=["documents", "metadatas", "distances"],
        )
        vec_ids = vec_results["ids"][0]

        # BM25 检索 Top-10
        tokenized_query = query.lower().split()
        bm25_scores     = bm25.get_scores(tokenized_query)
        top10_bm25_idx  = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:10]
        bm25_ids        = [chunk_ids[i] for i in top10_bm25_idx]

        # RRF 融合，取 Top-3
        fused_ids = rrf_fusion(vec_ids, bm25_ids)[:3]

        for rank, cid in enumerate(fused_ids, 1):
            # 从 ChromaDB 取回内容
            res = collection.get(ids=[cid], include=["documents", "metadatas"])
            if not res["ids"]:
                continue
            doc  = res["documents"][0]
            meta = res["metadatas"][0]
            print(f"  [{rank}] chunk_id={cid}")
            print(f"      domain={meta.get('domain')}  section={meta.get('section_title', '')[:60]}")
            print(f"      time_sensitive={meta.get('time_sensitive', False)}", end="")
            if meta.get("time_sensitive"):
                print(f"  ⚠️  {meta.get('deadline_note', '')}", end="")
            print()
            print(f"      {doc[:120]}...")
            print()


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    all_chunks = build_vector_database()
    build_bm25_index(all_chunks)

    # 验证完成后取消下行注释，再次运行即可测试混合检索：
    # test_query()
