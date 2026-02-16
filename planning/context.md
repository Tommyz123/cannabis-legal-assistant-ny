# Context - 项目索引与状态

最后更新: 2026-02-15 | 项目阶段: [Production-Ready Prototype + Eval Engineering]

## 技术栈
Python + ChromaDB (向量) + BM25 (关键词) + OpenAI (GPT-4o-mini + text-embedding-3-small) + LangGraph + FastAPI

## 关键配置参数
| 参数 | 当前值 | 文件位置 |
|------|--------|---------|
| top_k | 8 | src/agent/core.py — query_node / review_node |
| min_score | 0.015 | src/agent/core.py — search() 调用处 |
| max_turns | 5 | src/agent/core.py — process() → get_history |
| max_messages | 10 | src/agent/conversation.py — FIFO 上限 |
| LLM | gpt-4o-mini, temperature=0.1 | src/agent/core.py / intent.py |
| embedding | text-embedding-3-small | src/retrieval/pipeline.py |
| 向量候选数 / BM25候选数 | 10 / 10 | src/retrieval/pipeline.py — search() |

## 稳定区（禁止改动）
- query.py / build_database.py / check_database.py — 原型脚本
- chroma_db/ + bm25_index.pkl — 数据层（cannabis_law_nyc 集合）

## 模块索引

### src/retrieval/pipeline.py — RetrievalPipeline / ChunkResult
- search(query_en, top_k=8, min_score=0.015) → list[ChunkResult]
- translate_if_chinese(text) → (original, en)
- build_context(chunks) → (context_str, warnings)  ← warnings 已去重（dict.fromkeys）
- 依赖: chroma_db/, bm25_index.pkl, OpenAI Embedding

### src/agent/intent.py — IntentClassifier
- classify(user_input, history) → "general_query" | "strategy_review"
- 关键词规则 → GPT-4o-mini 确认 → 历史延续（三段式）

### src/agent/conversation.py — ConversationManager
- create_session() → uuid_str
- add_message(session_id, role, content) → None
- get_history(session_id, max_turns=5) → list[dict]
- clear_session(session_id) → None

### src/agent/reviewer.py — StrategyReviewer / ReviewResult
- review(content, context_chunks) → ReviewResult
- 检测: 俚语 / 医疗声明 / 卡通儿童导向
- 固定提醒: 21+ / 500英尺 / 2026-02-24

### src/agent/core.py — AgentCore / AgentState / AgentResponse / SourceRef
- process(session_id, user_input) → AgentResponse
- _is_refusal(answer) → bool  ← 离题时清空 sources
- _build_retrieval_input(user_input, history) → str  ← 短查询(<15字)补全历史
- 路由: general_query → query_node | strategy_review → review_node

### src/agent/prompts.py
- SYSTEM_BASE / GENERAL_QUERY_PROMPT / STRATEGY_REVIEW_PROMPT

### main.py — CLI 入口
- python main.py（交互模式）/ python main.py "问题"（单次查询）

### eval/golden_dataset.json — 黄金数据集（2026-02-15 新建）
- 20 道测试题，独立于代码，人工可直接编辑
- 包含 version、pass_criteria（通过阈值）、test_cases（id/category/question/required_keywords/ground_truth/expected_intent）
- 新增/修改题目只改此 JSON，不需要动 Python 代码

### eval_accuracy.py — 准确性评估脚本（2026-02-13 新增，2026-02-15 改造）
- 从 `eval/golden_dataset.json` 加载测试题和阈值（不再硬编码）
- `PassCriteria` dataclass：keyword_rate_min / llm_score_min / questions_pass_min / overall_llm_min / consistency_pass_min
- `TestCase` dataclass：含 `known_issue: bool`（区分系统缺陷 vs eval 配置问题）
- `RoundResult` dataclass：含 `intent_match: bool`（每轮 intent 比对）
- `QuestionResult` dataclass：含 `intent_accuracy: float`
- `load_dataset(json_path)` → `(list[TestCase], PassCriteria)`（同时返回测试题和阈值）
- `load_test_cases(json_path)` → `list[TestCase]`（向后兼容 wrapper）
- `build_agent()` → `tuple[AgentCore, OpenAI]`
- `run_question(agent, llm_client, tc, n_rounds, criteria)` → `QuestionResult`
- `generate_report(results, n_rounds, criteria)` → 写 `reports/ACCURACY_EVAL_REPORT.md` + 归档
- 报告 8 个 Section：Overview / Summary（动态阈值）/ Category / Bottom3 / Consistency / Findings（known_issue 分离）/ FAIL详情 / Intent Accuracy
- 运行：`venv/Scripts/python.exe eval_accuracy.py [--rounds N]`

### C:\Users\zhi89\Desktop\llm_eval_framework\ — 通用 Eval 框架（2026-02-15 新建）
- 独立工具包，与项目解耦，可复制到任意新项目使用
- `core.py`：通用层（PassCriteria / TestCase / RoundResult / QuestionResult / load_dataset / keyword_check / llm_judge / consistency_score / generate_report）— 禁止改动
- `runner_template.py`：项目适配层，只改 STEP1 `build_agent()` 和 STEP2 `get_answer()`
- `golden_dataset_template.json`：数据集模板
- `README.md`：AI 可读的接入指南（含黄金数据集设置方法、常见坑）
- 接入新项目：将 core.py 复制为 `{project}/core.py`，runner_template.py 改名为 `eval_accuracy.py`

### comprehensive_eval.py — 自动化基准测试
- 用于生成 REAL_EVALUATION_REPORT.md
- 测试指标：意图准确率、检索命中率、合规审查率、延迟

### eval_run.py — 手动场景评估
- 对应 EVALUATION_REPORT.md 的 14 个测试场景
- 仅打印输出，无自动断言

### src/api/server.py — FastAPI
- GET /api/health | POST /api/session | DELETE /api/session/{id} | POST /api/chat
- CORS 已启用 / lifespan 初始化

### src/agent/reviewer.py — StrategyReviewer / ReviewResult（2026-02-15 更新）
- violation detail 字段改为双语格式：`"Prohibited slang violation (检测到禁用俚语): ..."` 等
- 其余接口不变

### reports/ — 测试与评估报告
- `reports/ACCURACY_EVAL_REPORT.md`：最新一次准确性评估（每次运行覆盖）
- `reports/archive/`：历史评估报告，按时间戳命名（ACCURACY_EVAL_YYYY-MM-DD_HHmm.md）
- `reports/REALENV_TEST_REPORT.md`：2026-02-13 真实环境 E2E 测试报告（11 场景，10 passed 1 xfailed）

### knowledge/ — 法律法规源文件 (Markdown)
- 14 份原始文档，作为 RAG 检索系统的 Ground Truth
- 包含：01_General_Regs, 02_Packaging, 09_Marketing 等

### tests/ — 44个单元测试 + 11个E2E测试
- 44 个单元测试（mock）：test_api.py / test_conversation.py / test_intent.py / test_pipeline.py / test_reviewer.py / test_agent_core.py
- `tests/test_realenv.py`：11 个真实环境 E2E 测试（真实 uvicorn + httpx + OpenAI API）
  - 场景：服务器启动、健康检查、Session 生命周期、中/英文查询、策略审查、多轮对话、短查询丰富、离题拒答、错误处理
  - 运行命令：`venv/Scripts/python.exe -m pytest tests/test_realenv.py -v -s`（端口 8001）

## 依赖关系
```
Task1(检索) → Task2(意图)  ┐
Task1        → Task3(对话) ├→ Task5(AgentCore) → Task6(CLI)
Task1        → Task4(审查) ┘                   → Task7(API)
```

## 已知限制（非代码问题）
- **高延迟**：法规检索平均耗时 ~9s，主因是同步阻塞 I/O (OpenAI + ChromaDB) 阻塞了 Event Loop
- **数据持久化**：Session 存储在内存中，重启服务会导致对话历史丢失
- Q4 罚款金额：知识库以刑事处罚描述，无具体美元数字
- EDGE1 混合查询：中英混合输入时，税率检索被包装类 chunk 主导
- ChromaDB telemetry 警告：cosmetic，不影响功能

## 环境配置
- OS: Windows (WSL2)
- 虚拟环境路径: `venv/`
- 激活（CMD）: `venv\Scripts\activate`
- Python 直接调用: `venv/Scripts/python.exe`
- 测试命令: `venv/Scripts/python.exe -m pytest tests/ -v`（注意使用 Windows 路径格式）
- 禁止使用系统 Python（`/usr/bin/python3`）
