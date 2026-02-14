# 计划：Cannabis Law Assistant - RAG 向量数据库构建

## Context
项目目录 `/mnt/c/Users/zhi89/Desktop/Cannabis_Law_Assistant/` 当前只有 18 个 Markdown 文档（14个法规知识文件 + 4个非知识文件）。
用户希望根据 `AI_Legal_Assistant_Database_Design_Report.md` 的设计方案，构建一个本地 RAG 向量数据库（方案A：ChromaDB + LangChain + OpenAI Embedding），在虚拟环境中开发，便于后续接入 AI 法律顾问问答系统。

**环境确认：**
- WSL Ubuntu，Python 3.12.3 位于 `/usr/bin/python3`
- 有 OpenAI API Key
- 用同目录下新建 `venv/` 虚拟环境（参考 AI_Agent 项目的模式）
- 项目目录当前无任何 Python 文件

---

## 需要新建的文件（3个）

```
Cannabis_Law_Assistant/
├── requirements.txt        # Python 依赖（版本锁定）
├── .env.example            # 环境变量模板
└── build_database.py       # 主构建脚本
```

> `venv/` 和 `chroma_db/` 目录由用户命令和脚本运行时自动生成，无需代码创建。

---

## 文件详细内容

### 1. requirements.txt

```
langchain==0.3.18
langchain-community==0.3.17
langchain-openai==0.3.6
openai==1.63.2
chromadb==0.6.3
tiktoken==0.9.0
python-dotenv==1.0.1
rank_bm25==0.2.2
```

**版本注意：**
- ChromaDB 0.6.x 使用新 API：`chromadb.PersistentClient(path=...)` 而非旧的 `Settings(persist_directory=...)`
- langchain 0.3.x 与 openai 1.x SDK 配套使用
- `rank_bm25`：为混合检索提供 BM25 关键词索引支持

---

### 2. .env.example

```
# 复制此文件为 .env 并填入真实值
OPENAI_API_KEY=sk-your-openai-api-key-here
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION_NAME=cannabis_law_nyc
EMBEDDING_MODEL=text-embedding-3-small
KNOWLEDGE_DIR=.
```

---

### 3. build_database.py 核心结构

```
build_database.py
├── DOCUMENT_METADATA 字典（14个文件的元数据定义，含 keywords、time_sensitive）
├── count_tokens()           # tiktoken 计算 token 数
├── load_and_split_file()    # 读取单文件 + MarkdownHeaderTextSplitter + 二次切分
├── build_vector_database()  # 主构建函数（读取→分块→嵌入→存储 ChromaDB）
├── build_bm25_index()       # 构建 BM25 关键词索引（持久化为 bm25_index.pkl）
└── test_query()             # 可选：测试混合检索验证
```

**分块策略：**
1. `MarkdownHeaderTextSplitter`：按 `##` 和 `###` 标题切分（`strip_headers=False` 保留标题语义）
2. 若块 > 600 tokens，用 `RecursiveCharacterTextSplitter` 二次切分（chunk_size≈1800字符，**overlap≈250字符**）
3. 过滤 < 50 字符的空块

> overlap 从原设计的 150 字符提升至 **250 字符（约 13%）**，减少法律条款跨段落时的语义断裂。

**每块元数据字段：**
- `doc_id`、`file_name`、`domain`、`jurisdiction`、`audience`（字符串，逗号分隔）
- `section_title`、`chunk_index`、`chunk_id`（格式：`{doc_id}__{index:03d}`）、`token_count`
- `keywords`（字符串，逗号分隔，来自 DOCUMENT_METADATA，用于检索增强）
- `time_sensitive`（布尔值：`True` / `False`，标记含截止日期的 chunk）
- `deadline_note`（字符串，仅当 `time_sensitive=True` 时写入，说明具体时效内容）

**ChromaDB 关键配置：**
- `hnsw:space: cosine`（余弦距离，适合文本语义检索）
- 集合已存在则先删除再重建（支持重复运行）
- 批量存储，每批 50 块（避免 API 单次请求过大）

**BM25 索引：**
- 构建完 ChromaDB 后，同步将所有 chunk 文本写入 `BM25Okapi` 索引
- 持久化为 `bm25_index.pkl`（`pickle` 序列化），供查询时复用
- 索引与 ChromaDB 共用同一份 `chunk_id` 列表，确保对齐

**混合检索策略（供后续查询脚本使用）：**
```
查询文本
  ├── 向量检索（ChromaDB cosine）→ Top-10
  └── BM25 关键词检索（rank_bm25）→ Top-10
        ↓
  RRF 融合（Reciprocal Rank Fusion，k=60）
        ↓
  最终 Top-3 chunk → 送入 LLM
```
> 混合检索对法律文本尤为重要：精确条款编号（如 `Section 280E`、`Part 129`）靠 BM25 匹配，语义近似问题（如"未成年人购买处罚"）靠向量检索，两者互补。

**14个知识文件对应 domain 及 keywords：**

| 文件 | domain | keywords（关键检索词） |
|------|--------|----------------------|
| 01_General_Regs.md | general | license, OCM, conditional adult-use, CAURD, dispensary |
| 02_Packaging_Labeling.md | packaging | label, child-resistant, THC symbol, warning, packaging |
| 03_Security_Storage.md | security | surveillance, vault, alarm, storage, restricted access |
| 04_Retail_Operations.md | retail | POS, inventory, METRC, track-and-trace, adult-use |
| 05_Official_Guidance.md | guidance | OCM guidance, FAQ, policy, proximity, buffer zone |
| 06_FDNY_Fire_Code.md | fire_safety | FDNY, fire code, storage limit, permit, CO2 |
| 07_Tax_Guidance.md | tax | 280E, COGS, excise tax, sales tax, quarterly filing |
| 08_Labor_Rights.md | labor | minimum wage, WARN Act, cannabis labor peace, union |
| 09_Marketing_Advertising.md | marketing | advertising, social media, billboard, Part 129, 2026-02-24 |
| 09_Violations_Penalties.md | violations | penalty, fine, revocation, suspension, enforcement |
| 10_Laboratory_Testing.md | testing | COA, cannabinoid, contaminant, batch testing, Part 130 |
| 12_NYC_DCWP_License.md | nyc_license | DCWP, NYC license, local permit, zoning |
| 15_Consumer_Protection.md | consumer_protection | consumer right, return, recall, complaint, disclosure |
| COMPLIANCE_CHECKLIST.md | compliance | checklist, audit, inspection, renewal, compliance |

**时效性内容标记（`time_sensitive=True` 的 chunk）：**

| 涉及文件 | 时效内容 | deadline_note |
|---------|---------|--------------|
| 05_Official_Guidance.md | proximity 测量标准 | Proximity measurement standard expires 2026-02-15 |
| 09_Marketing_Advertising.md | 广告牌过渡期 | Billboard transition deadline: 2026-02-24 |

> 包含上述时效内容的 chunk 在写入 ChromaDB 时设置 `time_sensitive=True`，查询脚本检测到此字段后应在 LLM prompt 中注入警告："⚠️ 该内容含有截止日期，请确认是否已过期。"

**两个 09_ 文件说明：**
> 不重命名原文件，通过 `doc_id` 唯一标识（`09_marketing_advertising` vs `09_violations_penalties`），ChromaDB 主键用 `chunk_id`，不会冲突。

**排除的文件（不向量化）：**
- README.md、PROJECT_SUMMARY.md、CHANGELOG.md、AI_Legal_Assistant_Database_Design_Report.md

---

## 用户运行步骤

```bash
# 1. 进入项目目录
cd /mnt/c/Users/zhi89/Desktop/Cannabis_Law_Assistant

# 2. 创建虚拟环境
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 创建 .env 并填入 API Key
cp .env.example .env
# 编辑 .env，将 OPENAI_API_KEY 改为真实 Key

# 6. 运行构建脚本
python build_database.py
```

**预期结果：**
- 生成 `chroma_db/` 目录（ChromaDB 持久化存储）
- 生成 `bm25_index.pkl`（BM25 关键词索引）
- 约 155-172 个向量块
- 预计 OpenAI API 花费 < $0.002

---

## 验证方法

构建完成后，取消注释 `build_database.py` 末尾的 `test_query()` 调用，再次运行：
```bash
python build_database.py
```
验证要点：
1. 返回 Top 3 相关法规内容，domain/section 符合预期
2. 测试精确条款查询（如 `"Section 280E deductible expenses"`），确认 BM25 能精准命中
3. 测试含时效性内容的查询（如 `"proximity measurement"`），确认返回 chunk 带有 `time_sensitive=True`

---

## 关键技术细节

- **ChromaDB 0.6.x API**：必须用 `chromadb.PersistentClient(path=...)` 而非旧版 `Settings`
- **元数据类型限制**：ChromaDB 仅支持 str/int/float/bool，audience/keywords 列表转为逗号分隔字符串，`time_sensitive` 存为 bool
- **两个 09_ 文件**：不重命名原文件，通过 `doc_id` 唯一标识
- **编码**：读取文件统一用 `encoding="utf-8"` 避免 Windows GBK 问题
- **token 上限**：text-embedding-3-small 最大 8191 tokens，二次切分确保不超限
- **overlap 提升**：250 字符（原 150），减少法律条款跨段落语义断裂
- **混合检索**：向量检索 + BM25 通过 RRF 融合，法律精确术语匹配靠 BM25，语义理解靠向量，两者互补
- **时效性警告**：`time_sensitive=True` 的 chunk 检索到后，查询层需注入截止日期警告，防止 AI 给出过期法律建议

---

## 方案评估对比（供参考）

| 维度 | 本方案（ChromaDB 混合检索） | 纯向量方案 | 云方案（Pinecone） |
|------|--------------------------|-----------|-----------------|
| 适合规模 | ~200 chunk，本地原型 | 同左 | 万级 chunk，多用户 |
| 精确术语匹配 | ✅ BM25 覆盖 | ❌ 可能漏召回 | ✅（需额外配置） |
| 时效性处理 | ✅ 字段标记 | ❌ 无 | 取决于实现 |
| 基础设施成本 | $0（本地） | $0 | ~$70/月起 |
| 复杂度 | 中 | 低 | 高 |
| 推荐用途 | 当前阶段 ✅ | 仅做最简 demo | 生产上线后 |
