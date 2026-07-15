# AI 客服项目 12 讲学习文档实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成 `docs/project_learning_12_lessons.md`，完整收录已输出的前两讲，并基于当前仓库补齐第三讲至第十二讲。

**Architecture:** 课程沿 `/api/chat` 主请求链路由外到内展开，再延伸到基础设施、评测和面试表达。只新增教学文档，不修改业务代码、配置、测试或依赖。

**Tech Stack:** Markdown、Mermaid、PowerShell、curl、pytest、FastAPI 项目现有脚本。

## Global Constraints

- 永远使用中文。
- 第一讲和第二讲必须保留当前任务中的原始文本。
- 第三讲至第十二讲只描述当前仓库真实存在的实现。
- 明确 mock、fallback、placeholder 与生产接入边界。
- 不声称 Demo 支持生产级高并发。
- 不把本地 eval 或 load report 当作生产指标。
- 不新增业务代码、依赖、环境变量或前端页面。

---

### Task 1: 建立课程文档并收录前两讲

**Files:**
- Create: `docs/project_learning_12_lessons.md`

**Interfaces:**
- Consumes: 当前任务中第一讲和第二讲的完整原始回答。
- Produces: 课程标题、学习说明、课程目录以及未经改写的第一讲和第二讲。

- [x] **Step 1: 建立文档开头**

写入总标题、课程定位、阅读方法、12 讲目录和能力边界；课程说明不能改变前两讲正文。

- [x] **Step 2: 原样写入第一讲**

从“好，我们开始第 1 讲”到“下一讲我们讲第 2 讲”完整写入，保留原有标题、列表、代码块、路径和话术。

- [x] **Step 3: 原样写入第二讲**

从“第二讲：`/api/chat` 接口层与数据契约”到最后两个自测题完整写入，保留 Mermaid、表格、curl 和状态码说明。

- [x] **Step 4: 检查前两讲标题**

Run: `rg -n "第 1 讲|第二讲" docs/project_learning_12_lessons.md`

Expected: 同时找到第一讲和第二讲正文标题。

### Task 2: 编写主编排、意图路由、RAG 与 LLM 四讲

**Files:**
- Modify: `docs/project_learning_12_lessons.md`

**Interfaces:**
- Consumes: `app/agents/customer_agent.py`、`app/agents/intent_classifier.py`、`app/agents/router.py`、`app/rag/`、`app/llm/`、`app/agents/chains/`。
- Produces: 第三讲至第六讲，形成从 Agent 编排到回答生成的连续学习路径。

- [x] **Step 1: 编写第三讲 CustomerAgent 主编排**

覆盖组件初始化、`handle()` 顺序、提前返回、异常处理、`finally` trace 收尾、为什么主编排不放在 API 层，以及安全拦截 curl。

- [x] **Step 2: 编写第四讲意图识别与 Router**

覆盖规则优先、LLM 结构化 fallback、`intent/slots/confidence/reason`、低置信度兜底、15 类意图分发和 Tool/RAG 分流。

- [x] **Step 3: 编写第五讲 RAG**

覆盖加载、清洗、零宽断言分块、Embedding、候选召回、MMR、Rerank、TopK、sources、缓存和 Milvus/BGE fallback。

- [x] **Step 4: 编写第六讲 LLM 与 LCEL**

覆盖 BaseLLM、工厂、Mock/Qwen provider、RAG Answer Chain、引用约束、无来源拒答、temperature=0 和 Token/成本记录边界。

### Task 3: 编写 Tools、Memory、RBAC 与 Safety 四讲

**Files:**
- Modify: `docs/project_learning_12_lessons.md`

**Interfaces:**
- Consumes: `app/tools/`、`mock_business_service/`、`app/memory/`、`app/auth/`、`app/audit/`、`app/safety/`。
- Produces: 第七讲至第十讲，解释业务系统集成、会话状态和治理能力。

- [x] **Step 1: 编写第七讲 Tools 与业务边界**

覆盖 Tool、BusinessClient、Mock/HTTP client、用户/套餐/账单/工单/Offer/Order、超时重试熔断、权限和 `tool_calls`。

- [x] **Step 2: 编写第八讲 Memory**

覆盖 `user_id + session_id` 隔离、最近 8 轮、Summary Buffer、key facts、指代改写、Redis fallback、TTL 与隐私处理。

- [x] **Step 3: 编写第九讲 RBAC 与 Audit**

覆盖 Role、Permission、AuthContext、普通用户自查、客服代查、管理员边界、目标用户、脱敏和 audit/trace 区别。

- [x] **Step 4: 编写第十讲 Safety**

覆盖关键词、正则、语义 detector、风险等级、ALLOW/REVIEW/BLOCK、输入/输出/工具参数、review queue 和 prompt injection。

### Task 4: 编写可观测性、评测与最终面试两讲

**Files:**
- Modify: `docs/project_learning_12_lessons.md`

**Interfaces:**
- Consumes: `app/events/`、`app/observability/`、`evals/`、`scripts/`、`docs/interview_guide.md`、`docs/demo_script.md`。
- Produces: 第十一讲、第十二讲以及完整学习闭环。

- [x] **Step 1: 编写第十一讲 Event、Trace 与 Metrics**

覆盖事件与 trace 的区别、Mock producer、RocketMQ placeholder、ContextVar、span、latency breakdown、trace 回放和 Prometheus-compatible `/metrics`。

- [x] **Step 2: 编写第十二讲 Eval、Load Report 与面试讲法**

覆盖评测数据集、Top1/Top3/TopK、source coverage、hallucination 简化指标、intent/tool/safety、延迟/Token/成本、压测报告和 30 秒/2 分钟/5 分钟表达。

- [x] **Step 3: 增加最终复习清单**

列出启动、Demo、测试、eval、load test 的执行顺序，以及简历生产指标与当前仓库证据的对应边界。

### Task 5: 文档验收

**Files:**
- Verify: `docs/project_learning_12_lessons.md`

**Interfaces:**
- Consumes: 完整课程文档。
- Produces: 讲次完整、路径可定位、命令一致、口径克制的最终 Markdown 文件。

- [x] **Step 1: 验证 12 个讲次**

Run: `rg -n "^## .*第.*讲|^# .*第.*讲" docs/project_learning_12_lessons.md`

Expected: 能按顺序识别第 1 至第 12 讲，无缺失和重复正文。

- [x] **Step 2: 验证关键能力覆盖**

Run: `rg -n "CustomerAgent|IntentClassifier|RAG|LCEL|BusinessClient|Memory|RBAC|Safety|Trace|Metrics|Eval|Load" docs/project_learning_12_lessons.md`

Expected: 每项核心能力均至少出现一次，并有对应讲次解释。

- [x] **Step 3: 验证边界说明**

Run: `rg -n "mock|fallback|placeholder|本地.*生产指标|生产级高并发" docs/project_learning_12_lessons.md`

Expected: 明确出现能力边界；任何高并发表述只能用于否定或风险说明。

- [x] **Step 4: 运行交付材料测试**

Run: `pytest tests/test_delivery_materials.py -q`

Expected: 全部通过。

- [x] **Step 5: 检查改动范围**

Run: `git status --short`

Expected: 新增课程文档和计划文件；已有 `evals/reports/latest_report.*` 修改保持未覆盖、未丢失。
