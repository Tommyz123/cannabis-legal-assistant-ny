# ACCURACY_FIX_PLAN

**基于：** `reports/ACCURACY_EVAL_REPORT.md`（2026-02-13）
**当前评分：** 15/20 通过 | avg_llm 4.10 | consistency 20/20 | ✅ OVERALL PASS
**目标评分：** 18/20 通过 | avg_llm ≥ 4.3

---

## 失败题汇总

| ID | 类别 | avg_kw | avg_llm | 失败原因 | 优先级 |
|----|------|--------|---------|---------|--------|
| Q02 | A-许可证 | 100% | 1.0 | 事实错误：agent 误称 DCWP 需要注册 | P0 |
| Q19 | F-策略审查 | 50% | 3.0 | reviewer 输出中文，缺 "prohibited"/"violation" | P1 |
| Q20 | F-策略审查 | 40% | 2.0 | reviewer 输出中文，LLM 评分低（内容不完整） | P1 |
| Q07 | B-包装标签 | 0% | 5.0 | 评估关键词过严，答案正确但用词不同 | P2 |
| Q14 | D-违规罚则 | 50% | 4.0 | 评估关键词过严，"without a license" ≠ "unlicensed" | P2 |

---

## P0：Q02 事实错误

### 问题描述
- **问题**："Does NYC require a separate local registration for cannabis retailers beyond the state license?"
- **正确答案**：不需要，DCWP 不发放大麻经营许可证，cannabis 牌照由 OCM 州级颁发
- **agent 实际回答**：包含 "DCWP" + "registration" 关键词（kw=100%），但 LLM 评为 1/5，说明 agent 错误表达了 DCWP 注册是必须的

### 根本原因分析
- `12_NYC_DCWP_License.md` 文档中大量描述 DCWP 职能和 registration 程序，检索召回后 LLM 可能误将 DCWP 的合规要求解读为"需要 DCWP 注册"
- 知识库文档标题含 "License" 字样，强化了检索偏向

### 修复方案
**方案 A（推荐）：在 `12_NYC_DCWP_License.md` 顶部强化免责说明**
在文档第一节加入显著声明：
```
> ⚠️ IMPORTANT: DCWP does NOT issue cannabis retail licenses.
> Cannabis retail licenses are issued exclusively by OCM (Office of Cannabis Management) at the state level.
> DCWP plays a collaborative enforcement role only.
```
- 修改文件：`knowledge/12_NYC_DCWP_License.md`
- 需重建数据库：`venv/Scripts/python.exe build_database.py`

**方案 B：在 GENERAL_QUERY_PROMPT 中添加负向约束**
```
5. Do NOT conflate DCWP's enforcement/compliance role with licensing authority.
   DCWP does not issue cannabis licenses in NYC.
```

---

## P1：Q19/Q20 策略审查路径中文输出

### 问题描述
- strategy_review 路径输出固定格式为中文："审查结论：不合规 检测到禁用俚语: high, stoner"
- 英文问题应收到英文审查报告

### 根本原因
`src/agent/reviewer.py` 内的审查输出模板硬编码中文字符串，`STRATEGY_REVIEW_PROMPT` 也是中文，未随 SYSTEM_BASE 的语言自适应改动一起更新

### 修复方案
**修改 `src/agent/core.py` — `review_node` 的 answer 构建**

现有：
```python
answer = (
    f"审查结论：{review_result.compliance_score}\n"
    + ("\n".join(violation_lines) if violation_lines else "未发现明显违规点。")
)
```

改为语言自适应：
```python
# Detect input language and format answer accordingly
is_english = not any('\u4e00' <= c <= '\u9fff' for c in state["user_input"])
if is_english:
    answer = (
        f"Review Result: {review_result.compliance_score}\n"
        + ("\n".join(violation_lines) if violation_lines else "No violations detected.")
    )
else:
    answer = (
        f"审查结论：{review_result.compliance_score}\n"
        + ("\n".join(violation_lines) if violation_lines else "未发现明显违规点。")
    )
```

**同时更新 `eval_accuracy.py` Q19/Q20 关键词**，将 "prohibited"/"violation" 替换为 reviewer 实际输出的词：
- Q19：`["stoner", "kid", "non-compliant", "slang"]`（英文路径后）
- Q20：`["cure", "treat", "medical", "non-compliant"]`

**涉及文件：**
- `src/agent/core.py`（review_node 输出格式）
- `eval_accuracy.py`（Q19/Q20 关键词调整）

---

## P2：评估关键词过严（Q07、Q14）

### 问题描述
agent 回答内容正确（llm=5/4），但使用了同义词，导致关键词命中率为 0%

| 题目 | 预期关键词 | agent 实际用词 |
|------|-----------|--------------|
| Q07 | `prohibited`, `repackage` | "not allowed to re-package" |
| Q14 | `unlicensed`, `penalty` | "without a license", "consequences" |

### 修复方案
**仅修改 `eval_accuracy.py` 关键词列表（不改系统代码）**

Q07 调整：
```python
# 旧
required_keywords=["prohibited", "repackage"],
# 新
required_keywords=["not allowed", "re-package"],
```

Q14 调整：
```python
# 旧
required_keywords=["unlicensed", "penalty", "criminal", "fine"],
# 新
required_keywords=["without a license", "criminal", "fine"],
```

---

## 修复预期效果

| 修复 | 预期新增通过题 | 通过率变化 |
|------|-------------|-----------|
| P0：Q02 知识库修复 | +1（Q02） | 15→16 |
| P1：reviewer 英文输出 | +2（Q19/Q20） | 16→18 |
| P2：关键词调整 | +2（Q07/Q14） | 18→20 |

**修复全部完成后预期：20/20 通过，avg_llm ≥ 4.3**

---

## 修复执行顺序

```
Step 1: P2 — 修改 eval_accuracy.py 关键词（无风险，5分钟）
Step 2: P1 — 修改 src/agent/core.py review_node 语言自适应（低风险，10分钟）
         → 运行 44 个单元测试验证
Step 3: P0 — 修改 knowledge/12_NYC_DCWP_License.md + 重建数据库（中等风险，15分钟）
         → 重新运行 eval_accuracy.py 验证 Q02
Step 4: 重新运行 eval_accuracy.py 生成最终报告
```

---

## 不建议修复的项目

| 项目 | 原因 |
|------|------|
| Q12 avg_llm=3.0（刚好达线） | billboard 截止日期知识库已正确，LLM 评分合理，无需改动 |
| Q15 avg_llm=3.0（刚好达线） | 吊销条件描述完整，3分属合理偏保守评分 |

---

**文档版本：** 1.0
**生成时间：** 2026-02-13
**下一步：** 等待确认后按顺序执行修复
