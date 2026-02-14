# 大麻法律助手 (Cannabis Law Assistant) - 产品需求文档 (PRD)

**版本:** v1.3
**日期:** 2026-02-11
**状态:** 知识库完整，Agent 应用层开发中

---

## 1. 项目愿景 (Product Vision)

构建一个基于 RAG (检索增强生成) 的智能法律助手，专门服务于**纽约州大麻零售药房 (Dispensary)** 的企业主。
该助手不仅提供静态的法律条文查询，更充当"虚拟合规顾问"，能够指导用户完成**从开业申请准备到日常运营合规**的全流程，并具备对用户提出的商业策略（如广告文案）进行**合规性预审**的能力。

---

## 2. 核心用户场景 (User Stories)

### 场景 A：申请前的准备 (Pre-Application)
> "我是一个想开大麻店的小白，但我不知道第一步该做什么，也不知道要准备什么材料才能不被拒签。"
*   **需求**: 提供清晰的开业倒计时、商业计划书大纲、社区委员会通知模板、必备服务商清单。
*   **数据支撑**: `16_Pre_Application_Guide.md` ✅ 已向量化

### 场景 B：商业策略合规审查 (Strategic Compliance Check)
> "我写了一句广告文案'High 翻天，治愈失眠'，还配了个卡通图，我想问问这个能不能发 Instagram？"
*   **需求**: 用户输入具体的商业策略（广告、促销活动、装修方案），助手基于法规库（特别是 Part 129）进行审查，指出违规点（如：禁止卡通、禁止医疗声明、禁止俚语）并给出修改建议。
*   **数据支撑**: `09_Marketing_Advertising.md` ✅ 已向量化
*   **标准**: "Zero Risk"（零风险），严格依据已生效法规。

### 场景 C：日常运营咨询 (Operational Q&A)
> "税务局的人下周要来查账，我需要准备哪些文件？280E 条款对我有影响吗？"
*   **需求**: 快速检索税务、安保、劳工、库存追踪等具体法规，提供实操层面的 Checklist。
*   **数据支撑**: `07_Tax_Guidance.md`, `COMPLIANCE_CHECKLIST.md` ✅ 已向量化

---

## 3. 知识库现状 (Knowledge Base Status) ✅ 完整

**15 个文档，504 个 chunk，全部向量化完毕。**

| # | 文件名 | 领域 |
|---|--------|------|
| 1 | 01_General_Regs.md | 通用法规 |
| 2 | 02_Packaging_Labeling.md | 包装标签 |
| 3 | 03_Security_Storage.md | 安全存储 |
| 4 | 04_Retail_Operations.md | 零售运营 |
| 5 | 05_Official_Guidance.md | 官方指引 |
| 6 | 06_FDNY_Fire_Code.md | 消防规范 |
| 7 | 07_Tax_Guidance.md | 税务指引 |
| 8 | 08_Labor_Rights.md | 劳工权益 |
| 9 | 09_Marketing_Advertising.md | 营销广告 |
| 10 | 09_Violations_Penalties.md | 违规处罚 |
| 11 | 10_Laboratory_Testing.md | 实验室测试 |
| 12 | 12_NYC_DCWP_License.md | NYC 城市许可 |
| 13 | 15_Consumer_Protection.md | 消费者保护 |
| 14 | COMPLIANCE_CHECKLIST.md | 合规检查清单 |
| 15 | 16_Pre_Application_Guide.md | 申请前准备 |

---

## 4. 功能需求 (Functional Requirements)

### 4.1 核心对话系统

**已有基础（`query.py` CLI）：**
- ✅ 中英文自动检测与翻译
- ✅ 混合检索：向量（Top-10）+ BM25（Top-10）→ RRF 融合（Top-3）
- ✅ 时效性警告（临近截止日期自动标注）
- ✅ 法规来源引用（文件名、领域、章节标题）

**Agent 应用层新增需求：**
- 意图识别：区分"普通查询" vs "策略审查"两种模式
- 多轮对话：维护对话上下文，支持追问
- 结构化输出：结论 + 法规出处 + 实操建议，格式固定
- 时效性警告：在回答中突出标注截止日期临近的法规

### 4.2 策略审查模式 (Review Mode)

针对广告/营销内容触发专项审查 Prompt：
1. **禁用内容检测**: 卡通/儿童元素、医疗承诺、俚语（stoner, weed, pot 等）
2. **受众验证**: 提醒需证明 90% 受众为 21+（LDA 阈值）
3. **地理限制**: 提醒 500 英尺距离限制（学校、公园、图书馆）
4. **户外广告截止提醒**: 广告牌过渡期截止日期 2026-02-24

### 4.3 文档生成 (Document Generation) — 可选

助手可输出模板（如社区通知信草稿、合规检查清单）。

---

## 5. 技术架构 (Technical Stack)

### 5.1 已就绪基础设施

| 组件 | 实现 | 状态 |
|------|------|------|
| **向量数据库** | ChromaDB 0.6.3（本地，`./chroma_db/`） | ✅ |
| **BM25 索引** | rank-bm25（`./bm25_index.pkl`） | ✅ |
| **向量模型** | OpenAI `text-embedding-3-small` | ✅ |
| **检索策略** | 向量 + BM25 → RRF Fusion | ✅ |
| **LLM** | GPT-4o-mini（OpenAI API） | ✅ |
| **CLI 原型** | `query.py` | ✅ |

### 5.2 检索管道

```
用户问题（中/英文）
    ↓
[语言检测] 中文 → 翻译为英文
    ↓
[并行检索] 向量 Top-10 + BM25 Top-10
    ↓
[RRF Fusion] → Top-3 chunks
    ↓
[时效性检查] 标注 deadline 临近的 chunk
    ↓
[LLM 生成] GPT-4o-mini → 中文回答 + 来源引用
```

### 5.3 待开发（Agent 应用层）

| 组件 | 说明 | 优先级 |
|------|------|--------|
| 意图识别节点 | 判断"普通查询" / "策略审查" | 高 |
| 对话历史管理 | 多轮上下文维护 | 高 |
| Agent 主入口 | 替代 `query.py`，封装完整 Agent 流程 | 高 |
| Web 界面 / API | HTTP 接口或前端 UI | 中 |

---

## 6. 开发计划 (Next Steps)

1. **设计 Agent 架构**：确定使用 LangGraph / 自定义状态机 / 其他框架
2. **实现意图识别**：区分普通问答与策略审查，路由到不同处理分支
3. **实现多轮对话**：维护 session 级别的对话历史
4. **封装 Agent 主入口**：整合检索管道 + 意图路由 + LLM 生成
5. **（可选）Web 接口**：基于 FastAPI 提供 HTTP API

---

## 7. 质量标准与约束

*   **"Zero Risk" 原则**: 仅引用已生效法规，不包含提案规或待定规
*   **来源可追溯**: 每个 chunk 携带 `file_name`、`domain`、`jurisdiction`、`section_title` 元数据
*   **时效性管理**: 临近截止日期的 chunk 携带 `time_sensitive=True` 和 `deadline_note`
*   **数据更新频率**: 建议每季度审查，NYS 大麻法规仍在快速演变
