# Cannabis Law Assistant

纽约州大麻零售药房法律合规 AI 助手，基于 RAG（检索增强生成）架构构建，支持法规问答与广告营销内容合规审查。

**版本：** MVP v1.0
**完成日期：** 2026-02-12
**状态：** 生产就绪

---

## 项目概述

Cannabis Law Assistant 是一个专为纽约州大麻零售药房设计的法律合规助手，提供两类核心功能：

1. **法规问答（General Query）** — 基于 14 份权威法规文档，回答许可、包装、运营、税务等合规问题
2. **广告营销合规审查（Strategy Review）** — 自动检测广告/营销内容中的禁用俚语、医疗声明、儿童元素，并给出改进建议

### 核心技术

- **混合检索**：向量检索（ChromaDB）+ BM25 关键词检索 + RRF 融合排序
- **Agent 编排**：LangGraph StateGraph（降级至本地编排器）
- **LLM**：OpenAI GPT-4o-mini（生成）+ text-embedding-3-small（嵌入）
- **接口**：CLI 命令行 + FastAPI HTTP API
- **中英文**：支持中文输入，自动翻译后检索英文法规

---

## 项目结构

```
Cannabis_Law_Assistant/
├── main.py                     # CLI 主入口（交互模式 & 单次查询模式）
├── query.py                    # RAG 原型（稳定，禁止改动）
├── build_database.py           # 数据库构建脚本
├── check_database.py           # 数据库检查脚本
├── requirements.txt            # 核心依赖
├── .env                        # 环境变量（OPENAI_API_KEY）
│
├── src/
│   ├── retrieval/
│   │   └── pipeline.py         # RetrievalPipeline — 混合检索 + RRF 融合
│   ├── agent/
│   │   ├── intent.py           # IntentClassifier — 意图识别（规则 + LLM）
│   │   ├── conversation.py     # ConversationManager — 多轮会话管理
│   │   ├── reviewer.py         # StrategyReviewer — 广告内容合规审查
│   │   ├── core.py             # AgentCore — LangGraph 编排主入口
│   │   └── prompts.py          # Prompt 模板集中管理
│   └── api/
│       └── server.py           # FastAPI HTTP API
│
├── tests/
│   ├── conftest.py             # 共享 fixtures（Mock OpenAI / ChromaDB）
│   ├── test_pipeline.py        # Task 1: 检索管道测试（6 用例）
│   ├── test_intent.py          # Task 2: 意图识别测试（6 用例）
│   ├── test_conversation.py    # Task 3: 对话管理测试（6 用例）
│   ├── test_reviewer.py        # Task 4: 策略审查测试（6 用例）
│   ├── test_agent_core.py      # Task 5: Agent 核心测试（8 用例）
│   └── test_api.py             # Task 7: HTTP API 测试（12 用例）
│
├── knowledge/                  # 14 份原始法规 Markdown 文档
├── chroma_db/                  # ChromaDB 向量数据库（已构建）
└── bm25_index.pkl              # BM25 索引（已构建）
```

---

## 快速开始

### 1. 环境准备

```bash
# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install langgraph fastapi uvicorn pytest pytest-mock
```

### 2. 配置 API Key

创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 3. 验证数据库

```bash
# 检查 ChromaDB 向量数据库
python -c "import chromadb; c=chromadb.PersistentClient('./chroma_db'); print('ChromaDB OK:', len(c.list_collections()), 'collections')"

# 检查 BM25 索引
python -c "import pickle; d=pickle.load(open('bm25_index.pkl','rb')); print('BM25 OK:', len(d['chunk_ids']), 'chunks')"
```

如果数据库不存在，先构建：

```bash
python build_database.py
```

---

## 使用方式

### CLI 模式

**交互模式**（多轮对话）：

```bash
python main.py
```

示例对话：

```
Cannabis Law Assistant (输入 quit 退出)
您: 大麻包装有什么要求？
[结论] 根据 9 NYCRR Part 119-120，大麻产品包装须满足...
[来源] 02_Packaging_Labeling.md § Part 119

您: 帮我审查这个广告文案："Get High with our premium stoner products!"
[审查结果] 不合规 — 检测到以下问题：
  - prohibited_slang: 含禁用俚语 "High", "stoner"
[合规提醒]
  - 受众年龄验证：确保 90% 以上受众年龄 ≥ 21 岁
  - 地理限制：禁止在学校、托儿所 500 英尺范围内投放
  - 户外广告截止：2026-02-24 前须完成合规整改
```

**单次查询模式**：

```bash
python main.py "如何申请纽约州大麻零售许可证？"
```

### HTTP API 模式

启动服务器：

```bash
uvicorn src.api.server:app --reload --port 8000
```

API 端点：

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/session` | 创建会话 |
| DELETE | `/api/session/{id}` | 删除会话 |
| POST | `/api/chat` | 发送消息 |

**示例请求**：

```bash
# 1. 创建会话
curl -X POST http://localhost:8000/api/session
# 返回：{"session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}

# 2. 发送消息
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-session-id", "message": "大麻包装有什么要求？"}'
```

**响应格式**：

```json
{
  "intent": "general_query",
  "answer": "根据 9 NYCRR Part 119...",
  "sources": [
    {"file_name": "02_Packaging_Labeling.md", "domain": "packaging", "section_title": "Part 119"}
  ],
  "warnings": ["注意：Part 120 关于标签的规定已于 2025-12-01 更新"],
  "suggestions": ["建议咨询持牌合规顾问确认最新要求"]
}
```

---

## 模块说明

### RetrievalPipeline (`src/retrieval/pipeline.py`)

混合检索核心，融合向量检索与关键词检索：

- `search(query_en, top_k=3)` — 向量 Top-10 + BM25 Top-10 + RRF 融合，返回 `list[ChunkResult]`
- `translate_if_chinese(text)` — 中文检测与自动翻译
- `build_context(chunks)` — 拼接 LLM context，收集时效性警告

### IntentClassifier (`src/agent/intent.py`)

双层意图识别：

- 第一层：关键词规则（广告/文案/营销/促销/审查/ad/marketing）→ `strategy_review`
- 第二层：对话历史延续（上轮为策略审查时默认延续）
- 第三层：LLM 二次确认（模糊输入，降级策略可用）

### ConversationManager (`src/agent/conversation.py`)

内存态多轮会话管理：

- UUID session_id，ISO 8601 自动时间戳
- 最大 10 条消息 FIFO 丢弃策略
- `create_session()` / `add_message()` / `get_history()` / `clear_session()`

### StrategyReviewer (`src/agent/reviewer.py`)

广告内容规则化合规审查：

- 禁用内容检测：俚语（stoner/weed/pot/high/420）、医疗声明（治愈/疗效）、卡通/儿童元素
- 固定三项合规提醒：受众 21+（90% LDA 阈值）、500 英尺禁区、2026-02-24 户外广告截止

### AgentCore (`src/agent/core.py`)

LangGraph StateGraph 编排：

```
START → intent_node → route
  ├── general_query  → query_node  → response_node → END
  └── strategy_review → review_node → response_node → END
```

缺失 langgraph 时自动回退至本地编排器。

---

## 测试

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行全部测试
pytest tests/ -v

# 运行指定模块测试
pytest tests/test_pipeline.py -v
pytest tests/test_api.py -v

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=term-missing
```

测试覆盖：44 个测试用例，全部通过，全部使用 Mock 避免真实 API 调用。

---

## 知识库

基于 14 份纽约州大麻法规权威文档（~240KB），涵盖：

| 领域 | 主要文档 | 覆盖率 |
|------|---------|--------|
| 基础法规 (NYCRR Title 9) | 01_General_Regs.md | 90% |
| 包装标签 | 02_Packaging_Labeling.md | 90% |
| 安全存储 | 03_Security_Storage.md | 90% |
| 零售运营 | 04_Retail_Operations.md | 85% |
| **营销广告 (Part 129)** | 09_Marketing_Advertising.md | 95% |
| 实验室测试 (Part 130) | 10_Laboratory_Testing.md | 95% |
| NYC 城市许可 | 12_NYC_DCWP_License.md | 85% |
| 违规处罚 | 09_Violations_Penalties.md | 90% |
| 消费者保护 | 15_Consumer_Protection.md | 95% |
| 税务合规 | 07_Tax_Guidance.md | 95% |
| 劳工法规 | 08_Labor_Rights.md | 90% |
| 消防安全 | 06_FDNY_Fire_Code.md | 95% |

数据来源：Cornell LII、NYS OCM、NYC DCWP、NYC FDNY（仅包含已生效法规）

---

## 代码质量

| 模块 | Pylint | Bandit |
|------|--------|--------|
| src/retrieval/ | 8.56/10 | 无高危 |
| src/agent/intent.py | 9.58/10 | 无高危 |
| src/agent/conversation.py | 10.00/10 | 无高危 |
| src/agent/reviewer.py | 10.00/10 | 无高危 |
| src/agent/core.py | 9.09/10 | 无高危 |
| src/api/ | 9.19/10 | 无高危 |
| main.py | 10.00/10 | 无高危 |

---

## 依赖

```
langchain==0.3.18
langchain-openai==0.3.6
openai==1.63.2
chromadb==0.6.3
tiktoken==0.9.0
python-dotenv==1.0.1
rank_bm25==0.2.2
langgraph          # Agent 编排（可选，缺失时自动降级）
fastapi            # HTTP API
uvicorn            # ASGI 服务器
pytest             # 测试
pytest-mock        # Mock 外部 API
```

---

## 重要说明

- **API Key 安全**：OpenAI API Key 仅通过 `.env` 文件传入，不得硬编码
- **数据时效**：法规数据截止 2026-02-08，建议每季度审查更新
- **Zero Risk 原则**：所有 Prompt 包含「仅引用已生效法规」约束，禁止 LLM 编造法规内容
- **网络受限**：当网络不可用时，CLI 模式自动降级为 BM25 离线检索 + 本地摘要

---

## 版本历史

### MVP v1.0 (2026-02-12) — Agent 应用完成

- Task 1: RetrievalPipeline — 混合检索（向量 + BM25 + RRF）
- Task 2: IntentClassifier — 意图识别
- Task 3: ConversationManager — 多轮会话管理
- Task 4: StrategyReviewer — 广告合规审查
- Task 5: AgentCore — LangGraph 编排
- Task 6: CLI 主入口
- Task 7: FastAPI HTTP API

### Legal DB v2.0 (2026-02-08) — 知识库完成

- 14 份权威法规文档（~240KB）
- 法律覆盖率 85%，内容完整性 90%，整体评分 88/100
