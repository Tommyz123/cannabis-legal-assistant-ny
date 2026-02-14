"""
Cannabis Law Assistant - 数据库质量诊断脚本
检验向量数据库的分块质量、覆盖率、检索命中率

用法：
  python check_database.py
"""

import os
import pickle
import statistics

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()

OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME    = os.getenv("CHROMA_COLLECTION_NAME", "cannabis_law_nyc")
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
BM25_INDEX_PATH    = "./bm25_index.pkl"

SEP  = "=" * 65
SEP2 = "-" * 65


# ─────────────────────────────────────────────
# 1. 基本统计
# ─────────────────────────────────────────────
def check_basic_stats(index_data: dict):
    print(SEP)
    print("【1】基本统计")
    print(SEP)

    metadatas = index_data["metadatas"]
    texts     = index_data["texts"]
    total     = len(texts)

    print(f"  总 chunk 数：{total}")

    # 按文件统计
    from collections import Counter
    file_counts = Counter(m["file_name"] for m in metadatas)
    print(f"\n  各文件 chunk 数：")
    for fname, cnt in sorted(file_counts.items(), key=lambda x: -x[1]):
        print(f"    {fname:<35} {cnt:>4} 块")

    # token 分布
    token_counts = [m["token_count"] for m in metadatas]
    print(f"\n  Token 分布（每块）：")
    print(f"    最小值：{min(token_counts)}")
    print(f"    最大值：{max(token_counts)}")
    print(f"    平均值：{statistics.mean(token_counts):.1f}")
    print(f"    中位数：{statistics.median(token_counts):.1f}")
    print(f"    标准差：{statistics.stdev(token_counts):.1f}")

    # 字符数分布
    char_counts = [len(t) for t in texts]
    print(f"\n  字符数分布（每块）：")
    print(f"    最小值：{min(char_counts)}")
    print(f"    最大值：{max(char_counts)}")
    print(f"    平均值：{statistics.mean(char_counts):.1f}")

    # 异常块检测
    too_short = [(i, texts[i]) for i in range(total) if token_counts[i] < 30]
    too_long  = [(i, texts[i]) for i in range(total) if token_counts[i] > 700]
    print(f"\n  ⚠️  异常块检测：")
    print(f"    过短块（< 30 tokens）：{len(too_short)} 个")
    print(f"    过长块（> 700 tokens）：{len(too_long)} 个")

    if too_short:
        print(f"\n  过短块示例：")
        for idx, t in too_short[:3]:
            print(f"    [{metadatas[idx]['chunk_id']}] {repr(t[:80])}")
    if too_long:
        print(f"\n  过长块示例：")
        for idx, t in too_long[:3]:
            print(f"    [{metadatas[idx]['chunk_id']}] tokens={metadatas[idx]['token_count']}  {repr(t[:80])}")


# ─────────────────────────────────────────────
# 2. 元数据完整性检查
# ─────────────────────────────────────────────
def check_metadata(index_data: dict):
    print(f"\n{SEP}")
    print("【2】元数据完整性")
    print(SEP)

    metadatas = index_data["metadatas"]
    required_fields = ["doc_id", "file_name", "domain", "jurisdiction",
                       "audience", "keywords", "chunk_id", "chunk_index",
                       "token_count", "time_sensitive"]

    missing_any = 0
    for m in metadatas:
        for field in required_fields:
            if field not in m:
                print(f"  ❌ 缺少字段 '{field}'：chunk_id={m.get('chunk_id')}")
                missing_any += 1

    if missing_any == 0:
        print(f"  ✅ 所有 {len(metadatas)} 个 chunk 元数据字段完整")

    # 时效性 chunk 检查
    ts_chunks = [m for m in metadatas if m.get("time_sensitive") == True]
    print(f"\n  时效性标记（time_sensitive=True）：{len(ts_chunks)} 个 chunk")
    for m in ts_chunks:
        print(f"    [{m['chunk_id']}] {m.get('deadline_note', '无备注')}")

    # domain 覆盖
    from collections import Counter
    domains = Counter(m["domain"] for m in metadatas)
    print(f"\n  Domain 分布（{len(domains)} 个领域）：")
    for domain, cnt in sorted(domains.items()):
        print(f"    {domain:<25} {cnt:>4} 块")


# ─────────────────────────────────────────────
# 3. 分块内容抽样检查
# ─────────────────────────────────────────────
def check_sample_chunks(index_data: dict):
    print(f"\n{SEP}")
    print("【3】分块内容抽样（每领域随机抽 1 块）")
    print(SEP)

    metadatas = index_data["metadatas"]
    texts     = index_data["texts"]

    # 每个 domain 取第一个 chunk
    seen_domains = set()
    samples = []
    for i, m in enumerate(metadatas):
        domain = m["domain"]
        if domain not in seen_domains:
            seen_domains.add(domain)
            samples.append((i, m, texts[i]))

    for idx, meta, text in samples:
        print(f"\n  [{meta['domain']}] {meta['file_name']} | {meta['section_title'][:50]}")
        print(f"  chunk_id={meta['chunk_id']}  tokens={meta['token_count']}")
        # 打印前 300 字符
        preview = text[:300].replace("\n", " ")
        print(f"  内容预览：{preview}{'...' if len(text) > 300 else ''}")
        print(SEP2)


# ─────────────────────────────────────────────
# 4. 检索命中率测试
# ─────────────────────────────────────────────
def check_retrieval(collection, embeddings, index_data: dict):
    print(f"\n{SEP}")
    print("【4】检索命中率测试（10 个典型问题）")
    print(SEP)

    from rank_bm25 import BM25Okapi

    bm25      = index_data["bm25"]
    chunk_ids = index_data["chunk_ids"]
    metadatas = index_data["metadatas"]
    id_to_meta = {m["chunk_id"]: m for m in metadatas}

    def rrf(vec_ids, bm25_ids, k=60):
        scores = {}
        for r, cid in enumerate(vec_ids):
            scores[cid] = scores.get(cid, 0) + 1 / (k + r + 1)
        for r, cid in enumerate(bm25_ids):
            scores[cid] = scores.get(cid, 0) + 1 / (k + r + 1)
        return sorted(scores, key=lambda x: scores[x], reverse=True)

    # 测试集：(问题, 期望命中的 domain 或关键词)
    TEST_CASES = [
        ("cannabis packaging child-resistant requirements",          "packaging"),
        ("Section 280E federal tax deduction cannabis",              "tax"),
        ("METRC track and trace inventory system",                   "retail"),
        ("FDNY fire code cannabis storage limit",                    "fire_safety"),
        ("billboard advertising transition deadline",                "marketing"),
        ("proximity measurement buffer zone school",                 "guidance"),
        ("laboratory testing COA batch cannabinoid contaminant",     "testing"),
        ("DCWP New York City local license permit",                  "nyc_license"),
        ("penalty fine license revocation enforcement",              "violations"),
        ("minimum wage WARN Act labor rights dispensary employee",   "labor"),
    ]

    hits = 0
    for query, expected_domain in TEST_CASES:
        # 向量检索
        vec   = embeddings.embed_query(query)
        vres  = collection.query(query_embeddings=[vec], n_results=10, include=["metadatas"])
        vids  = vres["ids"][0]

        # BM25 检索
        toks  = query.lower().split()
        bscores = bm25.get_scores(toks)
        bidx  = sorted(range(len(bscores)), key=lambda i: bscores[i], reverse=True)[:10]
        bids  = [chunk_ids[i] for i in bidx]

        # RRF Top-3
        top3  = rrf(vids, bids)[:3]
        top3_domains = [id_to_meta[cid]["domain"] for cid in top3 if cid in id_to_meta]

        hit = expected_domain in top3_domains
        if hit:
            hits += 1
        status = "✅" if hit else "❌"
        got = ", ".join(top3_domains)
        print(f"  {status} [{expected_domain:<18}] 实际 Top-3 domain: {got}")
        if not hit:
            print(f"     查询：{query}")

    print(f"\n  命中率：{hits}/{len(TEST_CASES)} = {hits/len(TEST_CASES)*100:.0f}%")
    if hits == len(TEST_CASES):
        print("  ✅ 所有测试全部命中，检索质量优秀！")
    elif hits >= 8:
        print("  ✅ 命中率良好。")
    elif hits >= 6:
        print("  ⚠️  命中率一般，可考虑调整分块参数或 embedding 模型。")
    else:
        print("  ❌ 命中率较低，建议检查分块策略。")


# ─────────────────────────────────────────────
# 5. chunk_id 唯一性检查
# ─────────────────────────────────────────────
def check_uniqueness(index_data: dict):
    print(f"\n{SEP}")
    print("【5】chunk_id 唯一性检查")
    print(SEP)

    chunk_ids = index_data["chunk_ids"]
    unique    = set(chunk_ids)
    if len(chunk_ids) == len(unique):
        print(f"  ✅ 所有 {len(chunk_ids)} 个 chunk_id 唯一，无重复。")
    else:
        from collections import Counter
        dups = [cid for cid, cnt in Counter(chunk_ids).items() if cnt > 1]
        print(f"  ❌ 发现 {len(dups)} 个重复 chunk_id：")
        for d in dups[:10]:
            print(f"    {d}")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
def main():
    print(SEP)
    print("Cannabis Law Assistant - 数据库质量诊断")
    print(SEP)

    # 加载 BM25 索引
    with open(BM25_INDEX_PATH, "rb") as f:
        index_data = pickle.load(f)

    # 加载 ChromaDB
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    collection    = chroma_client.get_collection(COLLECTION_NAME)

    # 加载 Embedding（检索测试用）
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)

    # 运行各项检查
    check_basic_stats(index_data)
    check_metadata(index_data)
    check_sample_chunks(index_data)
    check_uniqueness(index_data)
    check_retrieval(collection, embeddings, index_data)

    print(f"\n{SEP}")
    print("诊断完成。")
    print(SEP)


if __name__ == "__main__":
    main()
