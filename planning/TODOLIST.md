# Cannabis Law Assistant - 开发任务清单

**关联文档:** PROJECT_PLAN_v1.md
**生成时间:** 2026-02-11
**总任务数:** 7

---

## 进度追踪

| 指标 | 状态 |
|------|------|
| 总进度 | 100% (7/7) |
| P0 任务 | 6/6 完成 |
| P1 任务 | 1/1 完成 |

| Task | 名称 | 优先级 | 状态 |
|------|------|--------|------|
| Task 1 | 检索管道模块重构 | P0 | 已完成 |
| Task 2 | 意图识别模块 | P0 | 已完成 |
| Task 3 | 对话管理模块 | P0 | 已完成 |
| Task 4 | 策略审查模块 | P0 | 已完成 |
| Task 5 | Agent 核心模块 | P0 | 已完成 |
| Task 6 | CLI 主入口 | P0 | 已完成 |
| Task 7 | FastAPI HTTP API | P1 | 已完成 |

---

## 任务依赖关系

```
Task 1 (检索管道)
  │
  ├──→ Task 2 (意图识别)
  │
  ├──→ Task 3 (对话管理)
  │
  └──→ Task 4 (策略审查)
         │
         ├──→ Task 5 (Agent 核心) ←── Task 2, Task 3
         │
         └──→ Task 6 (CLI 主入口) ←── Task 5
                │
                └──→ Task 7 (FastAPI API) ←── Task 5
```

**依赖说明:**
- Task 1 无依赖，可立即开始
- Task 2, 3, 4 依赖 Task 1（需要检索管道接口）
- Task 2, 3, 4 之间无依赖，可并行开发
- Task 5 依赖 Task 1, 2, 3, 4（整合所有模块）
- Task 6 依赖 Task 5（需要 Agent 核心接口）
- Task 7 依赖 Task 5（需要 Agent 核心接口）
- Task 6 和 Task 7 之间无依赖，可并行开发

---

## 共享数据类定义

以下数据类在多个 Task 中使用，在首次需要时创建：

### ChunkResult（Task 1 创建，位于 src/retrieval/pipeline.py）
```python
@dataclass
class ChunkResult:
    chunk_id: str           # chunk 唯一标识
    text: str               # chunk 文本内容
    score: float            # RRF 融合后分数
    file_name: str          # 来源文件名
    domain: str             # 领域分类
    section_title: str      # 章节标题
    time_sensitive: bool    # 是否时效性相关
    deadline_note: str      # 截止日期备注（可为空字符串）
```

### ReviewResult（Task 4 创建，位于 src/agent/reviewer.py）
```python
@dataclass
class ReviewResult:
    violations: list[dict]       # 违规列表 [{"type": str, "detail": str, "suggestion": str}]
    compliance_score: str        # "合规" 或 "不合规"
    reminders: list[str]         # 合规提醒列表（受众21+、500英尺、截止日期）
```

### SourceRef（Task 5 创建，位于 src/agent/core.py）
```python
@dataclass
class SourceRef:
    file_name: str          # 来源文件名
    domain: str             # 领域分类
    section_title: str      # 章节标题
```

### AgentResponse（Task 5 创建，位于 src/agent/core.py）
```python
@dataclass
class AgentResponse:
    intent: str                  # "general_query" 或 "strategy_review"
    answer: str                  # 主要回答内容
    sources: list[SourceRef]     # 法规来源引用
    warnings: list[str]          # 时效性警告
    suggestions: list[str]       # 实操建议
```

### AgentState（Task 5 创建，位于 src/agent/core.py，LangGraph 状态）
```python
class AgentState(TypedDict):
    user_input: str              # 用户原始输入
    user_input_en: str           # 英文翻译版本
    session_id: str              # 会话 ID
    history: list[dict]          # 对话历史
    intent: str                  # 识别结果
    chunks: list[ChunkResult]    # 检索结果
    context: str                 # 拼接后的上下文
    warnings: list[str]          # 时效性警告
    answer: str                  # LLM 生成回答
    sources: list[SourceRef]     # 来源引用
    suggestions: list[str]       # 实操建议
    review_result: ReviewResult | None  # 审查结果（仅策略审查模式）
```

---

## 任务详情

### Task 1: 检索管道模块重构 (RetrievalPipeline)

**优先级:** P0
**依赖:** 无
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 从 `query.py` 提取混合检索逻辑（向量检索 + BM25 + RRF 融合），封装为独立的 `RetrievalPipeline` 类
2. 实现 `search(query_en: str, top_k: int = 3) -> list[ChunkResult]` 统一检索接口，返回结构化的 ChunkResult 数据对象
3. 实现 `translate_if_chinese(text: str) -> tuple[str, str]` 语言检测与翻译方法，复用已有的 `is_chinese()` 和 `translate_to_english()` 逻辑
4. 实现 `build_context(chunks: list[ChunkResult]) -> tuple[str, list[str]]` 上下文构建方法，从检索结果拼接 LLM context 并收集时效性警告

**实现位置:**
- 文件: `src/retrieval/__init__.py`, `src/retrieval/pipeline.py`
- 测试: `tests/test_pipeline.py`
- 配置: `tests/conftest.py`（共享 fixtures）

**conftest.py 共享 fixtures:**
```python
@pytest.fixture
def mock_openai_client(mocker):
    """Mock OpenAI 客户端，避免真实 API 调用"""

@pytest.fixture
def mock_chroma_collection(mocker):
    """Mock ChromaDB collection，返回预设检索结果"""

@pytest.fixture
def mock_bm25_index_data():
    """Mock BM25 索引数据，包含 bm25, chunk_ids, texts, metadatas"""

@pytest.fixture
def mock_embeddings(mocker):
    """Mock OpenAI Embeddings，返回固定向量"""

@pytest.fixture
def sample_chunk_result():
    """返回一个标准 ChunkResult 实例，供多个测试复用"""
```

**代码审核:**
```bash
pylint src/retrieval/
bandit -r src/retrieval/
```

**测试验证:**
```bash
pytest tests/test_pipeline.py -v
```
测试用例:
- test_hybrid_search_returns_results: 验证混合检索返回非空结果
- test_hybrid_search_top_k: 验证返回数量 = top_k
- test_rrf_fusion_scoring: 验证 RRF 融合排序正确性
- test_translate_if_chinese_detects: 验证中文检测准确
- test_translate_if_chinese_passthrough: 验证英文直接通过
- test_build_context_with_warnings: 验证时效性警告收集

**验收标准:**
- [x] `RetrievalPipeline` 类实现完成，接口与 PROJECT_PLAN 维度5 定义一致
- [x] 从 `query.py` 提取的逻辑无功能退化（检索流程保持一致：向量+BM25+RRF）
- [x] 所有 6 个测试用例通过
- [x] pylint 评分 ≥ 8.0（8.56/10）
- [x] bandit 无高危漏洞（仅低/中风险 pickle 提示）
- [x] `src/` 和 `tests/` 目录结构正确创建（含 `__init__.py`）

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 8.56/10, bandit 无高危）
2. [x] 确认全部测试通过（pytest tests/test_pipeline.py -v）
3. [x] 更新进度：Task 1 → 已完成，总进度 → 14%
4. [x] 检查 Task 2, 3, 4 前置条件已满足，可以开始

---

### Task 2: 意图识别模块 (IntentClassifier)

**优先级:** P0
**依赖:** Task 1
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 实现 `IntentClassifier` 类，提供 `classify(user_input: str, history: list[dict]) -> str` 方法，返回 `"general_query"` 或 `"strategy_review"`
2. 实现基于关键词的规则匹配层：检测广告、文案、营销、促销、审查等关键词，匹配则返回 `strategy_review`
3. 实现基于 LLM 的二次确认层：对模糊意图调用 GPT-4o-mini 进行判断，提高识别准确率
4. 支持通过对话历史上下文辅助意图判断（如上一轮是策略审查，追问默认延续该模式）

**实现位置:**
- 文件: `src/agent/__init__.py`, `src/agent/intent.py`
- 测试: `tests/test_intent.py`

**代码审核:**
```bash
pylint src/agent/intent.py
bandit -r src/agent/intent.py
```

**测试验证:**
```bash
pytest tests/test_intent.py -v
```
测试用例:
- test_intent_general_query: 输入"大麻包装要求"返回 general_query
- test_intent_strategy_review_keyword: 输入"帮我审查这个广告文案"返回 strategy_review
- test_intent_strategy_review_marketing: 输入"我的营销方案合规吗"返回 strategy_review
- test_intent_context_continuation: 上一轮为 strategy_review 时追问延续
- test_intent_english_input: 英文输入正确识别
- test_intent_ambiguous_input: 模糊输入触发 LLM 二次确认

**验收标准:**
- [x] `IntentClassifier` 类实现完成，接口与 PROJECT_PLAN 维度5 定义一致
- [x] 关键词规则覆盖：广告、文案、营销、促销、审查、review、ad、marketing
- [x] 对话历史上下文辅助判断功能可用
- [x] 所有 6 个测试用例通过
- [x] pylint 评分 ≥ 8.0（9.58/10）
- [x] bandit 无高危漏洞

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 9.58/10, bandit 无高危）
2. [x] 确认全部测试通过（pytest tests/test_intent.py -v）
3. [x] 更新进度：Task 2 → 已完成，总进度 → 28%
4. [x] 检查 Task 5 前置条件（需 Task 1, 2, 3, 4 全部完成）

---

### Task 3: 对话管理模块 (ConversationManager)

**优先级:** P0
**依赖:** Task 1
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 实现 `ConversationManager` 类，使用内存字典（`dict[str, list[dict]]`）存储会话历史
2. 实现 `create_session() -> str` 方法，创建新会话并返回 UUID 格式的 session_id
3. 实现 `add_message(session_id, role, content) -> None` 方法，添加消息到指定会话，自动附加 ISO 8601 时间戳
4. 实现 `get_history(session_id, max_turns=5) -> list[dict]` 方法，返回最近 N 轮对话，超出 10 轮时 FIFO 丢弃最早消息
5. 实现 `clear_session(session_id) -> None` 方法，清除指定会话数据

**实现位置:**
- 文件: `src/agent/conversation.py`
- 测试: `tests/test_conversation.py`

**代码审核:**
```bash
pylint src/agent/conversation.py
bandit -r src/agent/conversation.py
```

**测试验证:**
```bash
pytest tests/test_conversation.py -v
```
测试用例:
- test_create_session_returns_uuid: 创建会话返回有效 UUID
- test_add_and_get_message: 添加消息后可正确获取
- test_get_history_max_turns: max_turns=3 时只返回最近3轮
- test_conversation_fifo_limit: 超过10轮时最早消息被丢弃
- test_clear_session: 清除会话后历史为空
- test_get_history_nonexistent_session: 查询不存在的 session 返回空列表

**验收标准:**
- [x] `ConversationManager` 类实现完成，接口与 PROJECT_PLAN 维度5 定义一致
- [x] UUID 格式的 session_id 生成正确
- [x] FIFO 丢弃策略在超过 10 轮时正确工作
- [x] 所有 6 个测试用例通过
- [x] pylint 评分 ≥ 8.0（10.00/10）
- [x] bandit 无高危漏洞

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 10.00/10, bandit 无高危）
2. [x] 确认全部测试通过（pytest tests/test_conversation.py -v）
3. [x] 更新进度：Task 3 → 已完成，总进度 → 42%
4. [x] 检查 Task 5 前置条件（需 Task 1, 2, 3, 4 全部完成）

---

### Task 4: 策略审查模块 (StrategyReviewer)

**优先级:** P0
**依赖:** Task 1
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 实现 `StrategyReviewer` 类，提供 `review(content: str, context_chunks: list[dict]) -> ReviewResult` 方法，对广告/营销内容执行合规审查（ReviewResult 字段定义见「共享数据类定义」章节）
2. 实现禁用内容检测：扫描卡通/儿童元素关键词、医疗承诺（治愈、疗效等）、俚语（stoner, weed, pot, high, 420 等），返回违规类型和具体位置
3. 实现合规提醒生成：自动附加受众验证提醒（90% ≥ 21+）、地理限制提醒（500英尺距离）、户外广告截止提醒（2026-02-24）
4. 实现构建专项审查 Prompt：将检索到的 Part 129 法规内容 + 用户提交的策略内容 + 审查规则，组合为 LLM 审查 Prompt
5. 创建 `src/agent/prompts.py` 文件，定义 Prompt 模板集中管理

**prompts.py 初始结构（Task 4 创建，Task 5 补充）:**
```python
# src/agent/prompts.py

SYSTEM_BASE = """你是纽约州大麻零售药房的法律合规助手..."""

STRATEGY_REVIEW_PROMPT = """
基于以下法规内容，审查用户提交的广告/营销策略：
{context}
用户提交内容：{content}
审查规则：...
"""

# 以下由 Task 5 补充
GENERAL_QUERY_PROMPT = ""  # Task 5 实现
```

**实现位置:**
- 文件: `src/agent/reviewer.py`, `src/agent/prompts.py`
- 测试: `tests/test_reviewer.py`

**代码审核:**
```bash
pylint src/agent/reviewer.py src/agent/prompts.py
bandit -r src/agent/reviewer.py
```

**测试验证:**
```bash
pytest tests/test_reviewer.py -v
```
测试用例:
- test_detect_prohibited_slang: 检测含"High"的文案返回 prohibited_slang 违规
- test_detect_medical_claim: 检测含"治愈失眠"的文案返回 medical_claim 违规
- test_detect_cartoon_element: 检测含"卡通"描述返回 cartoon_element 违规
- test_clean_ad_passes: 合规广告文案返回无违规
- test_compliance_reminders_included: 审查结果包含受众、地理、截止日期提醒
- test_review_prompt_construction: 验证审查 Prompt 正确拼接法规内容和审查规则

**验收标准:**
- [x] `StrategyReviewer` 类实现完成，接口与 PROJECT_PLAN 维度5 定义一致
- [x] 禁用内容检测覆盖：俚语（stoner, weed, pot, high, 420）、医疗声明、卡通/儿童元素
- [x] 三项合规提醒（受众21+、500英尺、2026-02-24截止）在每次审查中附加
- [x] 所有 6 个测试用例通过
- [x] pylint 评分 ≥ 8.0（10.00/10）
- [x] bandit 无高危漏洞

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 10.00/10, bandit 无高危）
2. [x] 确认全部测试通过（pytest tests/test_reviewer.py -v）
3. [x] 更新进度：Task 4 → 已完成，总进度 → 57%
4. [x] 检查 Task 5 前置条件（需 Task 1, 2, 3, 4 全部完成）

---

### Task 5: Agent 核心模块 (AgentCore + LangGraph)

**优先级:** P0
**依赖:** Task 1, Task 2, Task 3, Task 4
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 定义 `AgentState(TypedDict)` 作为 LangGraph 状态对象（字段定义见「共享数据类定义」章节）
2. 定义 `SourceRef`、`AgentResponse` 数据类（字段定义见「共享数据类定义」章节）
3. 实现 LangGraph 节点函数（每个函数接收 AgentState，返回状态更新 dict）：
   - `intent_node(state)`: 调用 IntentClassifier，写入 state["intent"]
   - `query_node(state)`: 调用 RetrievalPipeline 检索 + LLM 生成，写入 answer/sources/warnings
   - `review_node(state)`: 调用 StrategyReviewer 审查，写入 answer/sources/warnings/suggestions
   - `response_node(state)`: 格式化输出，记录对话历史
4. 构建 `StateGraph(AgentState)`，添加节点和条件边：
   ```
   START → intent_node → route（条件边）
     ├→ intent == "general_query"   → query_node → response_node → END
     └→ intent == "strategy_review" → review_node → response_node → END
   ```
5. 实现 `AgentCore` 类作为封装层：
   - `__init__`: 依赖注入 RetrievalPipeline, IntentClassifier, ConversationManager, StrategyReviewer，编译 StateGraph
   - `process(session_id, user_input) -> AgentResponse`: 构建初始 AgentState，调用 graph.invoke()，返回 AgentResponse
6. 补充 `src/agent/prompts.py` 中的 `GENERAL_QUERY_PROMPT` 模板

**实现位置:**
- 文件: `src/agent/core.py`, `src/agent/prompts.py`（补充普通查询 Prompt）
- 测试: `tests/test_agent_core.py`

**代码审核:**
```bash
pylint src/agent/core.py
bandit -r src/agent/core.py
```

**测试验证:**
```bash
pytest tests/test_agent_core.py -v
```
测试用例:
- test_process_general_query: 普通查询返回 intent=general_query 的 AgentResponse
- test_process_strategy_review: 策略审查返回 intent=strategy_review 的 AgentResponse
- test_process_records_history: 处理后对话历史正确记录
- test_process_includes_sources: 回答中包含法规来源引用
- test_process_includes_warnings: 时效性相关查询包含警告
- test_agent_response_structure: AgentResponse 包含 intent/answer/sources/warnings/suggestions 字段
- test_graph_routing_general: LangGraph 图对 general_query 路由到 query_node
- test_graph_routing_review: LangGraph 图对 strategy_review 路由到 review_node

**验收标准:**
- [x] `AgentCore` 类实现完成，内部使用 LangGraph StateGraph 编排流程
- [x] `AgentState` TypedDict 定义完整，包含所有必需字段
- [x] LangGraph 图编译成功，条件边路由正确（缺失 langgraph 时回退兼容编排）
- [x] 普通查询和策略审查两条路径均可正常执行
- [x] `AgentResponse` 和 `SourceRef` 数据类包含所有必需字段
- [x] 对话历史在每次交互后正确更新
- [x] 所有 8 个测试用例通过
- [x] pylint 评分 ≥ 8.0（9.09/10）
- [x] bandit 无高危漏洞

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 9.09/10, bandit 无高危）
2. [x] 确认全部测试通过（pytest tests/test_agent_core.py -v）
3. [x] 更新进度：Task 5 → 已完成，总进度 → 71%
4. [x] 检查 Task 6, 7 前置条件已满足，可以开始

---

### Task 6: CLI 主入口 (main.py)

**优先级:** P0
**依赖:** Task 5
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 实现 `main.py` 作为新的 CLI 入口，替代原有 `query.py`，初始化所有依赖（ChromaDB、BM25、OpenAI、Agent 模块）并启动交互循环
2. 实现交互模式：自动创建 session，循环接收用户输入，调用 `AgentCore.process()`，格式化打印 `AgentResponse`（结论 + 来源 + 警告 + 建议）
3. 实现单次查询模式：支持 `python main.py "问题"` 命令行传参，查询后直接退出
4. 实现优雅退出：支持 quit/q/exit/退出 命令和 Ctrl+C/EOF 信号处理

**实现位置:**
- 文件: `main.py`
- 测试: `tests/test_main.py`（可选，CLI 交互测试）

**代码审核:**
```bash
pylint main.py
bandit -r main.py
```

**测试验证:**
```bash
pytest tests/ -v --ignore=tests/test_main.py
python main.py "大麻包装有什么要求？"
```
测试用例:
- test_main_single_query_mode: 命令行传参模式正确执行并退出
- test_main_output_format: 输出包含结论、来源、警告（如有）
- 手动测试: 交互模式多轮对话功能

**验收标准:**
- [x] `main.py` 实现完成，可替代 `query.py` 作为主入口
- [x] 交互模式支持多轮对话，输出结构化格式
- [x] 单次查询模式正常工作
- [x] 优雅退出功能正常（quit/q/exit/退出/Ctrl+C）
- [x] pylint 评分 ≥ 8.0（10.00/10）
- [x] bandit 无高危漏洞

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 10.00/10, bandit 无高危）
2. [x] 确认手动测试通过（单次查询模式已验证，交互模式逻辑已实现）
3. [x] 更新进度：Task 6 → 已完成，总进度 → 85%
4. [x] 检查 Task 7 前置条件已满足（如需继续）

---

### Task 7: FastAPI HTTP API (api.py)

**优先级:** P1
**依赖:** Task 5
**状态:** 已完成（2026-02-12）

**功能要求:**
1. 实现 FastAPI 应用，提供 `POST /api/chat` 端点，接收 `ChatRequest` 请求体（session_id + message），调用 `AgentCore.process()` 返回 `ChatResponse`
2. 实现 `POST /api/session` 端点创建新会话，`DELETE /api/session/{id}` 端点清除会话，`GET /api/health` 端点健康检查
3. 实现 CORS 中间件配置，允许前端跨域访问
4. 实现启动时自动初始化 Agent 依赖（ChromaDB、BM25、OpenAI），使用 FastAPI lifespan 管理生命周期

**实现位置:**
- 文件: `src/api/__init__.py`, `src/api/server.py`
- 测试: `tests/test_api.py`

**代码审核:**
```bash
pylint src/api/
bandit -r src/api/
```

**测试验证:**
```bash
pytest tests/test_api.py -v
```
测试用例:
- test_health_endpoint: GET /api/health 返回 200 + healthy
- test_create_session: POST /api/session 返回 session_id
- test_chat_endpoint: POST /api/chat 返回 ChatResponse 格式
- test_delete_session: DELETE /api/session/{id} 返回 200
- test_chat_missing_session: 缺少 session_id 返回 400
- test_cors_headers: 响应包含 CORS 头

**验收标准:**
- [x] FastAPI 应用实现完成，4 个端点均可正常访问
- [x] `ChatResponse` 格式与 PROJECT_PLAN 维度6 API 文档定义一致
- [x] CORS 中间件正确配置
- [x] 所有 6 个测试用例通过（当前环境 anyio 下为 12 项）
- [x] pylint 评分 ≥ 8.0（9.19/10）
- [x] bandit 无高危漏洞

**完成后必须执行:**
1. [x] 确认代码审核通过（pylint 9.19/10, bandit 无高危）
2. [x] 确认全部测试通过（pytest tests/test_api.py -v）
3. [x] 更新进度：Task 7 → 已完成，总进度 → 100%
4. [x] 确认所有 Task 完成，项目 MVP 交付

---

## 首次执行指令

开始开发前，执行以下初始化命令：

```bash
# 0. 激活虚拟环境（所有命令必须在 venv 中执行）
source venv/bin/activate

# 1. 创建项目目录结构
mkdir -p src/agent src/retrieval src/api tests

# 2. 创建 __init__.py 文件
touch src/__init__.py src/agent/__init__.py src/retrieval/__init__.py src/api/__init__.py tests/__init__.py

# 3. 安装新增依赖（在 venv 中）
pip install langgraph fastapi uvicorn pytest pytest-mock pytest-cov pylint bandit

# 4. 验证已有基础设施
python -c "import chromadb; c=chromadb.PersistentClient('./chroma_db'); print(f'ChromaDB OK: {len(c.list_collections())} collections')"
python -c "import pickle; d=pickle.load(open('bm25_index.pkl','rb')); print(f'BM25 OK: {len(d[\"chunk_ids\"])} chunks')"

# 5. 确认 OpenAI API Key 已配置
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('API Key:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING')"
```

---

## 工具说明

| 工具 | 用途 | 命令 |
|------|------|------|
| pytest | 运行测试 | `pytest tests/ -v` |
| pytest-cov | 测试覆盖率 | `pytest tests/ --cov=src --cov-report=term-missing` |
| pytest-mock | Mock 外部 API | 在测试中使用 `mocker` fixture |
| pylint | 代码静态分析 | `pylint src/` |
| bandit | 安全漏洞扫描 | `bandit -r src/` |
| uvicorn | FastAPI 开发服务器 | `uvicorn src.api.server:app --reload` |

---

## 注意事项

1. **API Key 安全**: OpenAI API Key 仅通过 `.env` 文件或环境变量传入，绝不硬编码在源码中
2. **Mock 外部调用**: 单元测试中必须 Mock OpenAI API 调用，避免产生真实费用和网络依赖
3. **保留原有代码**: `query.py`、`build_database.py`、`check_database.py` 保留不删除，`main.py` 作为新入口
4. **数据层不改动**: ChromaDB 和 BM25 索引为已有基础设施，本次开发仅读取不修改
5. **Zero Risk 原则**: 所有 Prompt 必须包含"仅引用已生效法规"约束，禁止 LLM 编造法规内容
6. **依赖顺序**: 严格按依赖关系开发，Task 1 必须最先完成，Task 5 必须在 1-4 全部完成后开始
7. **增量提交**: 每完成一个 Task 后建议 git commit，保持代码历史清晰
