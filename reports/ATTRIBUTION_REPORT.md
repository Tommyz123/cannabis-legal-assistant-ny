# 评估问题归因分析报告

**分析日期：** 2026-02-12
**基于：** EVALUATION_REPORT.md（综合评分 3.8/5）
**分析方法：** 逐一追溯问题到具体代码行，区分架构缺陷 vs 参数问题 vs 代码遗漏

---

## 归因总览

| # | 问题现象 | 根因分类 | 严重程度 | 涉及文件 |
|---|---------|---------|---------|---------|
| RC-1 | 精确数值检索失败（Q2/Q3/Q4） | 参数问题 + 架构缺陷 | 高 | pipeline.py, core.py |
| RC-2 | LLM 回答含糊、不提取具体数字 | 代码遗漏 | 高 | core.py, prompts.py |
| RC-3 | 多轮对话第 3 轮上下文漂移 | 架构缺陷 | 中 | core.py |
| RC-4 | 离题问题仍返回法规来源 | 架构缺陷 | 低 | pipeline.py, core.py |
| RC-5 | 回答语言不统一 | 代码遗漏 | 低 | core.py |

---

## RC-1：检索覆盖面不足（top_k=3 硬编码）

### 现象
- Q2「学校距离」：知识库有 500 英尺，回答为"保持一定的最小距离"
- Q3「开店成本」：知识库有 $220K-$900K，回答泛泛而谈
- Q4「未成年罚款」：检索到正确文档但未命中关键 chunk
- EDGE1：税率信息在 07_Tax_Guidance.md 中，完全未被检索到

### 根因定位

**代码位置：**
- `src/retrieval/pipeline.py:119` — `search()` 默认参数 `top_k=3`
- `src/agent/core.py:153` — `query_node` 硬编码调用 `self.retrieval.search(query_en, top_k=3)`
- `src/agent/core.py:170` — `review_node` 同样硬编码 `top_k=3`

**分析：**

检索管道从向量库取 Top-10 + BM25 取 Top-10，经 RRF 融合后**只保留 3 个 chunk**。这意味着：
- 融合池有 10-20 个候选 chunk，但 70-85% 被丢弃
- 需要精确数值的问题，数值可能在第 4-6 个 chunk 中
- 例如 Q3 的成本估算在 `05_Official_Guidance.md`，但检索命中了 `01_General_Regs.md`、`04_Retail_Operations.md`、`12_NYC_DCWP_License.md` 这三个更"通用"的文档，关键文档被挤出 Top-3

**top_k=3 为什么有问题：**
1. 信息密度低：法规问题往往涉及多个文档交叉引用（如距离要求同时出现在一般法规和 NYC 特定法规中）
2. RRF 偏向"泛相关"：通用文档在向量和 BM25 两个排名中都靠前，挤掉了精确但窄领域的文档
3. 单一查询覆盖不足：一个翻译后的英文查询无法同时匹配到所有相关术语

### 影响范围
法规问答 5 题中 3 题（Q2/Q3/Q4）直接受此影响，占 60%。

---

## RC-2：GENERAL_QUERY_PROMPT 定义了但未被使用（代码遗漏）

### 现象
- LLM 回答含糊，不提取上下文中的具体数字
- Q2 上下文中有 "500 feet" 但 LLM 回答"一定的最小距离"
- Q4 上下文中有罚款信息但 LLM 回答"建议查阅相关法律法规"

### 根因定位

**代码位置：**
- `src/agent/prompts.py:23-34` — 定义了 `GENERAL_QUERY_PROMPT` 模板
- `src/agent/core.py:134-149` — `_generate_general_answer()` **完全未使用该模板**

**实际使用的 Prompt（core.py:137-138）：**
```python
{"role": "system", "content": "你是大麻法规助手，仅基于提供上下文回答。"}
```

**定义但未使用的 Prompt（prompts.py:23-34）：**
```
请基于以下法规上下文回答用户问题：
回答要求：
1. 仅引用已生效法规内容
2. 结论清晰，必要时给出限制条件
3. 若上下文不足，明确说明需进一步核对原文
```

**对比原始 query.py 的 Prompt（query.py:174-181）：**
```
你是一位专业的纽约州大麻法律顾问，擅长解释纽约州及纽约市大麻相关法规。
回答要求：
1. 直接回答问题，引用具体法规条款或章节编号
2. 如有不确定之处，说明需进一步查阅原文
3. 如果检索内容与问题不相关，直接告知用户
4. 不要编造法规内容
```

**分析：**

这是典型的**重构时 Prompt 退化**。原始 `query.py` 有详细的 system prompt（要求"引用具体法规条款"），重构到 Agent 架构时：
1. `prompts.py` 中正确定义了 `GENERAL_QUERY_PROMPT`（但质量仍不如原版——缺少"引用具体条款编号"的指令）
2. `core.py` 的 `_generate_general_answer()` 方法**没有导入也没有使用** `GENERAL_QUERY_PROMPT`
3. 实际使用的是一句话的极简 system prompt，缺少任何"提取具体数字"的指令

即使检索到了包含 500 英尺的 chunk，没有明确指令的 LLM 倾向于给出模糊概述而非精确数值。

### 影响范围
所有法规问答（Q1-Q5）的回答质量。Q1 表现好是因为问题本身较明确、检索到的 chunk 信息集中。

---

## RC-3：多轮对话检索不感知历史上下文

### 现象
- 第 3 轮用户问"需要多长时间才能拿到？"，系统混入实验室测试时间（7-14 工作日），偏离了许可证申请话题

### 根因定位

**代码位置：**
- `src/agent/core.py:151-153` — `query_node` 的检索逻辑：
  ```python
  _, query_en = self.retrieval.translate_if_chinese(state["user_input"])
  chunks = self.retrieval.search(query_en, top_k=3)
  ```
- `src/agent/core.py:217-219` — `process()` 获取了 history 但**只传给 intent 分类**：
  ```python
  history = self.conversation.get_history(session_id, max_turns=5)
  ```

**分析：**

整个检索流程**完全不感知对话历史**：
1. `process()` 获取了 history，放入 initial_state
2. `intent_node` 使用 history 做意图识别 ✓
3. `query_node` **忽略 history**，只用 `state["user_input"]`（即"需要多长时间才能拿到？"）做检索 ✗
4. 翻译后变成类似 "How long does it take to get it?"——没有"许可证"上下文
5. 语义模糊的查询匹配到多个主题（实验室测试周期、许可证审批周期等）

**缺失的机制：**
- 无 Query Rewriting：应将"需要多长时间才能拿到？"→ 结合上文重写为"大麻零售许可证审批需要多长时间？"
- 无 History-Aware Retrieval：检索 query 中未包含历史关键词

### 影响范围
所有多轮追问场景，尤其是代词指代（"它"、"这个"、"多少"）和省略主语的问题。

---

## RC-4：缺少相关性阈值过滤

### 现象
- EDGE2 用户问"今天天气怎么样？"，系统返回 `10_Laboratory_Testing.md`、`09_Marketing_Advertising.md` 作为来源
- EDGE3 模糊问题"怎么办"返回猜测式回答而非追问

### 根因定位

**代码位置：**
- `src/retrieval/pipeline.py:147` — 直接取 top_k，不检查分数：
  ```python
  fused_ids = sorted(fused_scores, key=..., reverse=True)[:top_k]
  ```
- `src/agent/core.py:155-156` — 无条件构建 sources：
  ```python
  answer = self._generate_general_answer(...)
  sources = [self._chunk_to_source(chunk) for chunk in chunks]
  ```

**分析：**

1. RRF 融合后的分数**没有被用于过滤**。即使分数极低（说明完全不相关），也会被返回
2. `query_node` 无条件将所有检索到的 chunks 转为 sources 附在回答后面
3. 缺少一个"如果所有 chunk 分数低于阈值 → 不返回来源 / 触发追问"的逻辑

**对比 query.py 的处理（query.py:225-226）：**
```python
if not chunks:
    return "未找到相关法规内容，请尝试换一种表述方式。"
```
原版至少有一个"无结果时"的处理，但仍缺少分数阈值检查。

### 影响范围
所有离题和模糊查询场景。

---

## RC-5：回答语言控制缺失

### 现象
- EDGE1 中英文混合输入时，系统用英文回答包装要求部分

### 根因定位

**代码位置：**
- `src/agent/core.py:137` — system prompt 无语言指令：
  ```python
  {"role": "system", "content": "你是大麻法规助手，仅基于提供上下文回答。"}
  ```

**对比 query.py:175：**
```python
"请根据以下法规原文内容，用简洁、准确的中文回答用户问题。"
```

**分析：**

原始 `query.py` 明确要求"用中文回答"，但重构到 Agent 架构后这一指令丢失。当用户输入包含英文时，LLM 按输入语言跟随，用英文回答。

### 影响范围
所有包含英文的输入场景。

---

## 根因间的因果关系

```
RC-2（Prompt 退化）──┐
                    ├── 共同导致 → 法规问答 3.0/5
RC-1（top_k 过低）──┘

RC-3（检索不感知历史）── 直接导致 → 多轮对话 4.0/5

RC-4（无相关性阈值）──┐
                    ├── 共同导致 → 边界情况 3.3/5
RC-5（语言不受控）───┘
```

**RC-1 和 RC-2 是最核心的问题**，它们从两端（检索端 + 生成端）同时削弱了法规问答的质量：
- RC-1 导致关键信息不在 context 中
- RC-2 导致即使信息在 context 中，LLM 也不提取具体数值

---

## 改进优先级建议

| 优先级 | 修复项 | 预估工作量 | 预期提升 |
|--------|-------|-----------|---------|
| P0 | RC-2: 在 `_generate_general_answer` 中接入 `GENERAL_QUERY_PROMPT` 并增加"必须提取具体数字/金额/距离"的指令 | 0.5h | 法规问答 +0.5~1.0 分 |
| P0 | RC-1: top_k 从 3 提升至 5-8，参数化而非硬编码 | 0.5h | 法规问答 +0.5~1.0 分 |
| P1 | RC-3: 在 query_node 中加入 query rewriting（拼接历史关键词或用 LLM 重写查询） | 2h | 多轮对话 +0.5 分 |
| P2 | RC-4: 在 pipeline.search() 返回前加入最低分数阈值过滤 | 1h | 边界情况 +0.5 分 |
| P2 | RC-5: system prompt 中显式添加"用中文回答"指令 | 0.2h | 消除语言不一致 |

**预估优化后综合评分：** 3.8 → 4.3~4.5/5

---

## 附录：关键代码位置索引

| 文件 | 行号 | 说明 |
|-----|------|------|
| `src/retrieval/pipeline.py` | L119 | search() 的 top_k 默认值 |
| `src/retrieval/pipeline.py` | L147 | RRF 融合后截断，无阈值过滤 |
| `src/agent/core.py` | L134-149 | `_generate_general_answer()` — 未使用 GENERAL_QUERY_PROMPT |
| `src/agent/core.py` | L137 | 极简 system prompt，缺少精确提取指令 |
| `src/agent/core.py` | L151-153 | query_node 检索不感知对话历史 |
| `src/agent/core.py` | L153 | 硬编码 top_k=3 |
| `src/agent/core.py` | L170 | review_node 硬编码 top_k=3 |
| `src/agent/prompts.py` | L23-34 | GENERAL_QUERY_PROMPT 已定义但未被使用 |
| `query.py` | L174-181 | 原始版本的高质量 system prompt（对比参考） |
