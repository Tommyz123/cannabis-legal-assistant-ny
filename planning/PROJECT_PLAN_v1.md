# Cannabis Law Assistant - 项目计划书

**版本:** v1
**生成时间:** 2026-02-11
**项目阶段:** MVP期
**维度数:** 9

---

## 1. 项目概述

### 1.1 产品愿景

构建一个基于 RAG（检索增强生成）的智能法律助手 Agent，专门服务于纽约州大麻零售药房（Dispensary）企业主。在现有 CLI 检索原型（`query.py`）基础上，升级为具备**意图识别**、**多轮对话**和**策略合规审查**能力的智能 Agent 应用。

### 1.2 目标用户

| 用户类型 | 描述 |
|----------|------|
| 主要用户 | 纽约州大麻零售药房企业主（准备开业或已运营） |
| 次要用户 | 合规官、法律顾问、市场营销人员 |

### 1.3 核心价值

1. **一站式合规咨询**: 从开业申请到日常运营，覆盖全流程法律问题
2. **策略合规预审**: 对广告文案、促销活动等商业策略进行合规性审查
3. **精准法规检索**: 向量 + BM25 混合检索，RRF 融合排序，确保检索质量
4. **时效性预警**: 自动标注截止日期临近的法规，防止用户错过关键时间节点

### 1.4 项目类型

基于已有 RAG 基础设施（ChromaDB + BM25 + OpenAI Embedding），开发 Agent 应用层。属于**增量开发**项目。

---

## 2. 需求分析

### 2.1 功能需求

#### P0（必须实现）

| 编号 | 功能 | 描述 |
|------|------|------|
| F-01 | 意图识别 | 区分"普通查询"和"策略审查"两种模式，路由到不同处理分支 |
| F-02 | 多轮对话 | 维护 session 级别对话历史，支持追问和上下文关联 |
| F-03 | Agent 主入口 | 封装完整 Agent 流程，替代原有 `query.py` CLI |
| F-04 | 结构化输出 | 统一输出格式：结论 + 法规出处 + 实操建议 |
| F-05 | 策略审查模式 | 针对广告/营销内容触发专项审查（禁用内容检测、受众验证、地理限制、截止提醒） |

#### P1（建议实现）

| 编号 | 功能 | 描述 |
|------|------|------|
| F-06 | Web API 接口 | 基于 FastAPI 提供 HTTP API，支持外部系统对接 |
| F-07 | 文档生成 | 输出模板（社区通知信草稿、合规检查清单） |

### 2.2 非功能需求

| 类别 | 要求 | 方案 |
|------|------|------|
| 准确性 | "Zero Risk" 原则，仅引用已生效法规 | System Prompt 强制约束 + 检索源过滤 |
| 可追溯性 | 每个回答必须附带法规来源引用 | chunk 元数据携带 file_name、domain、section_title |
| 响应时间 | 单次查询 < 10 秒 | 本地 ChromaDB + 并行检索 |
| 安全性 | API Key 不硬编码 | 环境变量 + .env 文件 |
| 可维护性 | 知识库可独立更新 | 数据层与应用层分离 |

### 2.3 业务规则

1. 策略审查模式下必须检测：卡通/儿童元素、医疗承诺、俚语（stoner, weed, pot 等）
2. 广告审查必须提醒 90% 受众需为 21+（LDA 阈值）
3. 地理限制必须提醒 500 英尺距离限制（学校、公园、图书馆）
4. 户外广告牌过渡期截止日期 2026-02-24 必须在相关回答中标注
5. 中文输入自动翻译为英文进行检索，回答以中文输出

---

## 3. 系统架构

### 3.1 架构模式

采用**分层架构 + 状态机路由**模式：

- **数据层**: 已有的 ChromaDB 向量库 + BM25 关键词索引（不改动）
- **检索层**: 已有的混合检索管道（向量 + BM25 → RRF 融合）（复用）
- **Agent 层**: 新增意图识别 → 路由 → 对话管理 → LLM 生成
- **接口层**: CLI 入口 + FastAPI HTTP API

### 3.2 架构图

```
┌─────────────────────────────────────────────────────┐
│                    接口层 (Interface)                 │
│  ┌──────────────┐    ┌──────────────────────────┐   │
│  │  CLI 入口     │    │  FastAPI HTTP API (P1)   │   │
│  │  main.py     │    │  api.py                  │   │
│  └──────┬───────┘    └──────────┬───────────────┘   │
│         │                       │                    │
│         └───────────┬───────────┘                    │
│                     ▼                                │
│ ┌─────────────────────────────────────────────────┐ │
│ │              Agent 层 (Agent Core)               │ │
│ │                                                  │ │
│ │  ┌──────────────┐   ┌────────────────────────┐  │ │
│ │  │  意图识别     │──→│  路由分发                │  │ │
│ │  │  IntentNode  │   │  RouterNode            │  │ │
│ │  └──────────────┘   └───────┬────────────────┘  │ │
│ │                     ┌───────┴────────┐          │ │
│ │                     ▼                ▼          │ │
│ │          ┌──────────────┐  ┌──────────────────┐ │ │
│ │          │  普通查询     │  │  策略审查         │ │ │
│ │          │  QueryNode   │  │  ReviewNode      │ │ │
│ │          └──────┬───────┘  └────────┬─────────┘ │ │
│ │                 └────────┬──────────┘            │ │
│ │                          ▼                       │ │
│ │               ┌──────────────────┐               │ │
│ │               │  输出格式化       │               │ │
│ │               │  ResponseNode    │               │ │
│ │               └──────────────────┘               │ │
│ │                                                  │ │
│ │  ┌──────────────────────────────────────────┐   │ │
│ │  │  对话历史管理 (ConversationManager)        │   │ │
│ │  │  维护 session 级别多轮对话上下文           │   │ │
│ │  └──────────────────────────────────────────┘   │ │
│ └─────────────────────────────────────────────────┘ │
│                     │                                │
│                     ▼                                │
│ ┌─────────────────────────────────────────────────┐ │
│ │             检索层 (Retrieval Pipeline)           │ │
│ │                                                  │ │
│ │  用户问题 → 语言检测 → 翻译(中→英)               │ │
│ │      → 并行检索(向量Top-10 + BM25 Top-10)        │ │
│ │      → RRF Fusion → Top-3 chunks                │ │
│ │      → 时效性检查                                 │ │
│ └─────────────────────────────────────────────────┘ │
│                     │                                │
│                     ▼                                │
│ ┌─────────────────────────────────────────────────┐ │
│ │               数据层 (Data Store)                 │ │
│ │  ChromaDB (504 chunks)  +  BM25 Index (.pkl)    │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 3.3 数据流

```
用户输入 → 接口层(CLI/API) → Agent层.意图识别 → 路由分发
  ├→ 普通查询: → 检索层.混合检索 → LLM生成 → 结构化输出
  └→ 策略审查: → 检索层.混合检索(Part 129优先) → 审查Prompt → 合规报告输出
每轮交互: 对话历史管理器记录 → 下一轮携带上下文
```

### 3.4 SOLID 符合度

| 原则 | 实现方式 |
|------|---------|
| **S** 单一职责 | 每个 Node（IntentNode, QueryNode, ReviewNode, ResponseNode）只负责一项功能 |
| **O** 开放封闭 | 新增审查模式只需添加新 Node，不修改路由核心逻辑 |
| **L** 里氏替换 | 所有 Node 实现统一接口（输入 State → 输出 State） |
| **I** 接口隔离 | CLI 和 API 使用相同的 Agent 核心，但各自定义接口适配器 |
| **D** 依赖反转 | Agent 层依赖抽象的检索接口，不直接依赖 ChromaDB 实现细节 |

---

## 4. 技术栈选型

| 类别 | 选择 | 版本 | 备注（替代方案） |
|------|------|------|----------------|
| 编程语言 | Python | 3.11+ | - |
| LLM | GPT-4o-mini (OpenAI API) | latest | 替代: Claude, Gemini |
| 向量数据库 | ChromaDB | 0.6.3 | 替代: Pinecone, Weaviate（已就绪，不更换） |
| 向量模型 | text-embedding-3-small (OpenAI) | latest | 替代: text-embedding-3-large（已就绪，不更换） |
| 关键词检索 | rank-bm25 | 0.2.2 | 替代: Elasticsearch（已就绪，不更换） |
| Agent 框架 | LangGraph | 0.3.x | 替代: 自定义状态机 |
| Web 框架 | FastAPI | 0.115.x | 替代: Flask |
| 对话存储 | 内存字典（session_id → history） | - | 替代: Redis（MVP 阶段用内存即可） |
| 测试框架 | pytest | 8.x | 替代: unittest |
| 代码检查 | pylint + bandit | latest | - |

---

## 5. 核心模块设计

### 模块1: 意图识别模块 (IntentClassifier)

**职责**: 分析用户输入，判断属于"普通查询"还是"策略审查"模式。

**位置**: `src/agent/intent.py`

**接口**:
```python
class IntentClassifier:
    def classify(self, user_input: str, history: list[dict]) -> str:
        """
        返回 "general_query" 或 "strategy_review"
        """
```

**实现逻辑**:
- 基于关键词规则匹配（广告、文案、营销、促销 → strategy_review）
- 结合 LLM 进行二次确认（对模糊意图使用 GPT-4o-mini 判断）

**扩展点**: 可新增更多意图类型（如 "document_generation"）

### 模块2: 对话管理模块 (ConversationManager)

**职责**: 维护 session 级别的多轮对话历史，提供上下文窗口管理。

**位置**: `src/agent/conversation.py`

**接口**:
```python
class ConversationManager:
    def create_session(self) -> str:
        """创建新会话，返回 session_id"""

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """添加一条消息到会话历史"""

    def get_history(self, session_id: str, max_turns: int = 5) -> list[dict]:
        """获取最近 N 轮对话历史"""

    def clear_session(self, session_id: str) -> None:
        """清除指定会话"""
```

**实现逻辑**:
- 使用内存字典存储（`dict[str, list[dict]]`）
- 限制每个 session 最大保留 10 轮对话
- 超出限制时采用 FIFO 策略丢弃最早的对话

**扩展点**: 可替换为 Redis 或数据库持久化存储

### 模块3: Agent 核心模块 (AgentCore)

**职责**: 整合意图识别、检索管道、LLM 生成、对话管理，封装完整 Agent 流程。

**位置**: `src/agent/core.py`

**接口**:
```python
class AgentCore:
    def __init__(self, retriever, intent_classifier, conversation_manager):
        """注入依赖"""

    def process(self, session_id: str, user_input: str) -> AgentResponse:
        """
        完整处理流程:
        1. 获取对话历史
        2. 意图识别
        3. 路由到对应处理分支
        4. 执行检索 + LLM 生成
        5. 格式化输出
        6. 记录对话历史
        """
```

**数据结构**:
```python
@dataclass
class AgentResponse:
    intent: str                  # 识别到的意图
    answer: str                  # 主要回答内容
    sources: list[SourceRef]     # 法规来源引用
    warnings: list[str]          # 时效性警告
    suggestions: list[str]       # 实操建议（策略审查模式）
```

**扩展点**: 可通过新增处理分支支持更多模式

### 模块4: 策略审查模块 (StrategyReviewer)

**职责**: 针对广告/营销内容执行专项合规审查，输出合规报告。

**位置**: `src/agent/reviewer.py`

**接口**:
```python
class StrategyReviewer:
    def review(self, content: str, context_chunks: list[dict]) -> ReviewResult:
        """
        执行合规审查:
        1. 禁用内容检测（卡通、医疗承诺、俚语）
        2. 受众验证提醒（21+ LDA 阈值）
        3. 地理限制提醒（500英尺距离限制）
        4. 户外广告截止提醒（2026-02-24）
        """
```

**扩展点**: 可新增审查规则（如新法规生效时添加新检测项）

### 模块5: 检索管道模块 (RetrievalPipeline)

**职责**: 封装已有的混合检索逻辑（从 `query.py` 提取重构），提供统一检索接口。

**位置**: `src/retrieval/pipeline.py`

**接口**:
```python
class RetrievalPipeline:
    def __init__(self, chroma_collection, bm25_index_data, embeddings):
        """初始化检索管道"""

    def search(self, query_en: str, top_k: int = 3) -> list[ChunkResult]:
        """混合检索: 向量 Top-10 + BM25 Top-10 → RRF → Top-k"""

    def translate_if_chinese(self, text: str) -> tuple[str, str]:
        """语言检测与翻译，返回 (原文, 英文版本)"""
```

**扩展点**: 可调整检索参数（top_k、RRF 常数 k）或增加过滤条件

---

## 6. API 接口文档

### 6.1 内部接口（Agent Core）

Agent 核心对外暴露一个统一入口：

```python
POST /chat
```

### 6.2 HTTP API 端点（P1 - FastAPI）

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/chat` | 发送消息并获取回答 | `ChatRequest` | `ChatResponse` |
| POST | `/api/session` | 创建新会话 | - | `{"session_id": "xxx"}` |
| DELETE | `/api/session/{id}` | 清除会话 | - | `{"status": "ok"}` |
| GET | `/api/health` | 健康检查 | - | `{"status": "healthy"}` |

### 6.3 请求/响应格式

**ChatRequest**:
```json
{
  "session_id": "abc-123",
  "message": "大麻包装有什么要求？"
}
```

**ChatResponse**:
```json
{
  "intent": "general_query",
  "answer": "根据纽约州大麻法规...",
  "sources": [
    {
      "file_name": "02_Packaging_Labeling.md",
      "domain": "packaging",
      "section_title": "Child-Resistant Packaging Requirements"
    }
  ],
  "warnings": [],
  "suggestions": ["建议定期检查 OCM 官网获取最新包装要求更新"]
}
```

**ReviewResponse**（策略审查模式额外字段）:
```json
{
  "intent": "strategy_review",
  "answer": "您的广告文案存在以下合规问题...",
  "violations": [
    {
      "type": "prohibited_slang",
      "detail": "使用了俚语'High'，违反 Part 129 规定",
      "suggestion": "建议替换为中性描述"
    },
    {
      "type": "medical_claim",
      "detail": "'治愈失眠'构成医疗声明，违反广告规定",
      "suggestion": "删除医疗功效声明"
    }
  ],
  "compliance_score": "不合规",
  "sources": [...],
  "warnings": ["户外广告牌过渡期截止: 2026-02-24"]
}
```

---

## 7. 数据模型设计

### 7.1 已有数据（不改动）

**ChromaDB Collection**: `cannabis_law_nyc`
- 504 个 chunk
- 每个 chunk 携带元数据: doc_id, file_name, domain, jurisdiction, audience, keywords, section_title, chunk_index, chunk_id, token_count, time_sensitive, deadline_note

**BM25 Index**: `bm25_index.pkl`
- bm25 模型对象
- chunk_ids 列表
- texts 列表
- metadatas 列表

### 7.2 新增数据结构

**对话历史（内存）**:

| 字段 | 类型 | 描述 |
|------|------|------|
| session_id | str | 会话唯一标识（UUID） |
| messages | list[dict] | 消息列表 |
| messages[].role | str | "user" 或 "assistant" |
| messages[].content | str | 消息内容 |
| messages[].timestamp | str | ISO 8601 时间戳 |
| messages[].intent | str | 识别到的意图（仅 assistant 消息） |
| created_at | str | 会话创建时间 |

**Agent 状态（运行时）**:

| 字段 | 类型 | 描述 |
|------|------|------|
| user_input | str | 用户原始输入 |
| user_input_en | str | 英文翻译版本 |
| intent | str | 识别结果 |
| chunks | list[dict] | 检索到的 chunk 列表 |
| context | str | 拼接后的上下文文本 |
| warnings | list[str] | 时效性警告 |
| answer | str | LLM 生成的回答 |
| sources | list[dict] | 来源引用 |

### 7.3 数据流

```
用户输入 → (语言检测/翻译) → 英文查询
    → ChromaDB 向量检索 Top-10
    → BM25 关键词检索 Top-10
    → RRF 融合 → Top-3 chunks
    → 拼接 context + 对话历史 + 系统 Prompt
    → GPT-4o-mini 生成
    → 解析为 AgentResponse
    → 存入对话历史
    → 返回给用户
```

---

## 8. 项目结构

### 8.1 目录树

```
Cannabis_Law_Assistant/
├── src/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── core.py              # Agent 核心流程（AgentCore）
│   │   ├── intent.py            # 意图识别（IntentClassifier）
│   │   ├── conversation.py      # 对话历史管理（ConversationManager）
│   │   ├── reviewer.py          # 策略审查（StrategyReviewer）
│   │   └── prompts.py           # 所有 Prompt 模板集中管理
│   ├── retrieval/
│   │   ├── __init__.py
│   │   └── pipeline.py          # 检索管道（RetrievalPipeline）
│   └── api/
│       ├── __init__.py
│       └── server.py            # FastAPI 服务（P1）
├── tests/
│   ├── __init__.py
│   ├── test_intent.py           # 意图识别单元测试
│   ├── test_conversation.py     # 对话管理单元测试
│   ├── test_reviewer.py         # 策略审查单元测试
│   ├── test_pipeline.py         # 检索管道单元测试
│   ├── test_agent_core.py       # Agent 核心集成测试
│   └── conftest.py              # pytest fixtures
├── main.py                      # CLI 入口（替代 query.py）
├── knowledge/                   # 知识库文档（已有）
├── chroma_db/                   # ChromaDB 持久化目录（已有）
├── bm25_index.pkl               # BM25 索引（已有）
├── build_database.py            # 数据库构建脚本（已有）
├── check_database.py            # 数据库诊断脚本（已有）
├── query.py                     # 原 CLI 原型（保留，不再作为主入口）
├── requirements.txt             # Python 依赖
├── .env                         # 环境变量（不入库）
├── .env.example                 # 环境变量模板
└── docs/
    └── REQUIREMENTS.md          # 需求文档（已有）
```

### 8.2 目录说明

| 目录/文件 | 说明 |
|-----------|------|
| `src/agent/` | Agent 应用层核心代码，包含意图识别、对话管理、策略审查 |
| `src/retrieval/` | 检索管道，从 query.py 提取重构 |
| `src/api/` | FastAPI HTTP 接口（P1 优先级） |
| `tests/` | 全部测试文件，与源码模块一一对应 |
| `main.py` | 新的 CLI 入口，替代 query.py |
| `knowledge/` | 15 个知识库 Markdown 文档 |

---

## 9. 测试与验证策略

### 9.1 测试框架

| 工具 | 用途 |
|------|------|
| pytest | 单元测试 + 集成测试 |
| pytest-mock | Mock 外部 API 调用（OpenAI） |
| pylint | 静态代码分析 |
| bandit | 安全漏洞扫描 |

### 9.2 测试类型

| 测试类型 | 覆盖范围 | 预期用例数 |
|----------|---------|-----------|
| 单元测试 | IntentClassifier, ConversationManager, StrategyReviewer, RetrievalPipeline | 20+ |
| 集成测试 | AgentCore 完整流程（Mock LLM） | 5+ |
| 端到端测试 | CLI 交互 + API 请求（需真实 API Key） | 3+ |

### 9.3 关键测试用例

| 用例 | 描述 | 预期结果 |
|------|------|---------|
| test_intent_general_query | 输入"大麻包装要求" | 识别为 general_query |
| test_intent_strategy_review | 输入"帮我审查这个广告文案" | 识别为 strategy_review |
| test_conversation_history | 连续3轮对话后获取历史 | 返回3条记录 |
| test_conversation_max_turns | 超过10轮后获取历史 | 最早的消息被丢弃 |
| test_review_prohibited_slang | 输入含"High"的广告 | 检出 prohibited_slang 违规 |
| test_review_medical_claim | 输入含"治愈"的广告 | 检出 medical_claim 违规 |
| test_review_clean_ad | 输入合规广告文案 | 返回"合规" |
| test_pipeline_hybrid_search | 检索"packaging requirements" | 返回 packaging 领域 chunk |
| test_pipeline_chinese_input | 输入中文问题 | 正确翻译并检索 |
| test_agent_full_flow | 完整查询流程 | 返回结构化 AgentResponse |

### 9.4 验收标准

1. 所有单元测试通过（`pytest tests/ -v`）
2. pylint 评分 ≥ 8.0（`pylint src/`）
3. bandit 无高危漏洞（`bandit -r src/`）
4. 意图识别准确率 ≥ 90%（基于测试用例）
5. 检索命中率维持现有水平（≥ 80%）

### 9.5 测试命令

```bash
# 运行全部测试
pytest tests/ -v

# 运行单个模块测试
pytest tests/test_intent.py -v
pytest tests/test_conversation.py -v
pytest tests/test_reviewer.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_agent_core.py -v

# 代码质量检查
pylint src/
bandit -r src/

# 覆盖率报告
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 初步可行性评估

| 评估项 | 评分 (1-5) | 说明 |
|--------|-----------|------|
| 技术可行性 | 5 | 基础设施已就绪（ChromaDB + BM25 + OpenAI），Agent 层为增量开发 |
| 资源可行性 | 4 | 主要依赖 OpenAI API（有成本），其余为免费开源工具 |
| 时间可行性 | 4 | MVP 功能明确，模块边界清晰，可按模块逐步交付 |
| 风险可控性 | 4 | 主要风险为 LLM 幻觉（已通过 Zero Risk 原则 + 来源引用缓解） |

---

## 生成信息

- **生成工具**: Claude Code (project-workflow skill)
- **生成时间**: 2026-02-11
- **需求文档**: docs/REQUIREMENTS.md v1.3
- **项目阶段**: MVP期（代码 ~1019 行，核心模块 ≤ 2）
- **维度数**: 9
