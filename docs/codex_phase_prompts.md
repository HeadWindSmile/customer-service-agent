# 企业级 AI 客服问答系统：Codex 分阶段开发提示词手册

> 目标：把简历中的「客服问答系统」做成一个可运行、可演示、可讲清楚的企业级 Agent 面试项目。  
> 原则：不要一次性生成完整大项目。每个阶段都必须在上一阶段代码基础上增量开发，保证可启动、可测试、可回滚、可讲解。

---

## 一、项目最终定位

本项目不是普通 ChatBot，而是一个接入原有 Java/Spring Boot 业务系统的企业级 AI 客服中台 Demo。

最终要体现的核心能力：

1. FastAPI AI 服务层
2. LangChain / LCEL Agent 编排
3. RAG 知识库问答链路
4. Milvus / Chroma 向量检索适配
5. BGE Embedding + BGE Reranker 两阶段检索
6. 多轮上下文记忆
7. Redis 分布式会话隔离
8. 精准意图识别与 Router 路由
9. 业务工具调用
10. Spring Boot 业务系统边界模拟
11. RBAC 权限控制
12. 内容安全防护
13. RocketMQ 异步解耦
14. 可观测性与 trace 回放
15. AI 效果评测体系
16. Docker Compose 本地部署
17. README 和面试讲解材料

---

## 二、总体阶段规划

| 阶段 | 名称 | 核心目标 |
|---|---|---|
| 第 1 阶段 | 最小可运行企业骨架 | 跑通 `/api/chat`，完成目录结构、意图识别、路由、mock 工具、mock RAG |
| 第 2 阶段 | RAG 知识库链路 | 实现文档解析、分块、Embedding、向量入库、检索、来源引用 |
| 第 3 阶段 | LLM + LCEL 生成链路 | 接入 qwen-plus/OpenAI-compatible API，使用 LCEL 组织问答链 |
| 第 4 阶段 | 意图识别与多场景 Router | 从规则识别升级为结构化 LLM 意图识别，支持 slots/confidence |
| 第 5 阶段 | 业务工具调用与 Spring Boot 边界 | 模拟真实 Spring Boot 业务服务，AI 服务通过 HTTP 调用业务接口 |
| 第 6 阶段 | Redis 会话记忆与多轮上下文 | 实现 RedisMemory、Summary Buffer、最近 8 轮上下文、指代消解 |
| 第 7 阶段 | RBAC 权限与审计日志 | 用户/客服角色隔离，敏感操作鉴权，客服代查记录审计日志 |
| 第 8 阶段 | 内容安全防护体系 | 输入安全、输出安全、规则检测、LLM 语义检测接口预留、人工审核队列 |
| 第 9 阶段 | RocketMQ 异步解耦 | 工单创建、审计日志、AI 评测记录异步化 |
| 第 10 阶段 | 可观测性与评测体系 | trace_id、CallbackHandler、latency、token 成本、准确率、幻觉率评测 |
| 第 11 阶段 | 性能优化与部署 | Docker Compose、健康检查、连接池、缓存、压测脚本 |
| 第 12 阶段 | 面试交付材料 | README、架构图说明、接口文档、测试用例、面试讲解稿 |
| 第 13 阶段 | 简历成果映射与真实接入路线图 | 对齐简历生产项目能力、当前仓库证据、mock/fallback 边界和第 14-18 阶段真实接入路线 |
| 第 14 阶段 | RAG 真实检索增强 | 零宽断言分块、MMR、多候选召回、Reranker 抽象、BGE provider、Milvus 真实适配 |
| 第 15 阶段 | AI 评测体系增强 | Top1/Top3/TopK、幻觉、意图、工具、安全、延迟、Token 成本多维评测 |
| 第 16 阶段 | Offer / Order 业务域增强 | 新增商品 offer、订单 order 业务工具与业务服务契约 |
| 第 17 阶段 | 性能与可观测性增强 | Prometheus-compatible `/metrics`、性能报告、trace latency 字段、压测报告模板 |
| 第 18 阶段 | 最终面试演示闭环 | 统一 README、简历映射、演示脚本、评测报告、压测报告和讲解口径 |

---

## 三、每次让 Codex 开发前的固定要求

每一阶段都要在提示词最后追加以下约束：

```text
通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端页面。
```

---

# 第 1 阶段：最小可运行企业骨架

## 阶段目标

先做一个能启动、能请求、能根据不同问题走不同链路的企业级骨架。

第一阶段重点不是 RAG 精度，而是项目结构和主链路：

```text
POST /api/chat
  ↓
权限校验
  ↓
内容安全输入检查
  ↓
意图识别
  ↓
Router 路由
  ↓
RAG mock / 业务工具 mock
  ↓
内容安全输出检查
  ↓
记录 trace
  ↓
返回结构化结果
```

## 验收标准

1. `uvicorn app.main:app --reload` 可以启动。
2. `/api/chat` 可以正常调用。
3. 至少支持 6 类意图：
   - faq_query
   - package_query
   - package_change
   - bill_query
   - fault_diagnosis
   - ticket_create
4. 返回结构必须包含：
   - answer
   - intent
   - slots
   - sources
   - tool_calls
   - trace_id
   - latency_ms
5. 代码结构清晰，不是单文件 Demo。

## 给 Codex 的提示词

```text
你现在是一名资深 AI Agent 应用架构师 + Python/FastAPI 后端工程师。

我要构建一个用于 Agent 开发岗位面试的企业级 AI 客服问答系统 Demo。请严格按照我的简历项目内容生成第一阶段代码，不要自由发挥成普通 ChatBot。

项目背景：
公司已有 Java/Spring Boot 主业务系统，现在新增一层 Python/FastAPI AI 服务，构建“业务微服务 + AI 服务层（LLM + Agent）”融合架构。AI 服务面向 C 端用户和客服人员提供智能问答，覆盖业务咨询、套餐查询、套餐办理、账单查询、故障排查、售后工单创建等核心场景。

简历项目技术栈：
- Python 3.11
- FastAPI
- LangChain
- LCEL
- Milvus
- Redis Cluster
- MySQL 8.0
- 通义千问 qwen-plus
- Spring Boot 业务系统
- RocketMQ

第一阶段目标：
请先生成“最小可运行版本”，不要一次性生成完整大项目。第一阶段必须能启动、能调用 /api/chat、能根据不同用户问题走不同链路，并返回结构化结果。

第一阶段暂时要求：
1. FastAPI 项目可以通过 uvicorn app.main:app --reload 启动。
2. 提供 POST /api/chat 接口。
3. 请求体字段：
   - user_id
   - session_id
   - role
   - message
4. 响应体字段：
   - answer
   - intent
   - slots
   - sources
   - tool_calls
   - trace_id
   - latency_ms
5. 先用规则 + 简单 LLM mock 的方式实现 intent_classifier，不要第一版就强依赖真实大模型。
6. 先实现 6 类核心意图：
   - faq_query：业务咨询 / 知识库问答
   - package_query：套餐查询
   - package_change：套餐办理 / 套餐变更
   - bill_query：账单查询
   - fault_diagnosis：故障排查
   - ticket_create：售后工单创建
7. 实现 Router 路由机制：
   - faq_query 走 RAG 链路
   - package_query / bill_query / package_change / ticket_create 走业务工具调用
   - fault_diagnosis 可以先走 RAG + 工单创建建议
8. tools 层先用 mock 数据模拟 Spring Boot 业务系统接口，但代码结构必须像真实企业项目：
   - query_user_package(user_id)
   - query_bill(user_id, month)
   - change_package(user_id, target_package)
   - create_ticket(user_id, issue_type, description)
   - query_user_profile(user_id)
9. 注意：AI 服务不要直接操作业务数据库。业务工具层要模拟“通过内部 HTTP API 调用 Spring Boot 业务系统”的边界，第一版可以用 mock client，但接口命名和注释要体现真实调用关系。
10. rag 层先实现接口和 mock 文档检索，不要第一版就接 Milvus。需要预留 MilvusVectorStore 适配层，后续第二阶段再接入真实 Milvus。
11. memory 层先实现内存版会话记忆，保留最近 8 轮对话。需要预留 RedisMemory 实现类，后续替换为 Redis Cluster。
12. safety 层实现最小内容安全：
   - 输入敏感词检查
   - 输出敏感词检查
   - 禁止泄露用户隐私
   - 禁止编造资费承诺
13. auth / permission 层实现最小 RBAC：
   - role=user：只能查询自己的信息
   - role=agent：可以帮助用户查询，但要记录审计日志
14. observability 层实现：
   - trace_id 生成
   - 请求耗时 latency_ms
   - intent
   - slots
   - tool_calls
   - retrieved_sources
   - error 信息
   - 用统一 logger 输出结构化日志
15. 项目结构必须清晰，不能把逻辑都写在 main.py。

请生成如下目录结构：

customer-service-agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   └── chat.py
│   ├── schemas/
│   │   └── chat.py
│   ├── agents/
│   │   ├── customer_agent.py
│   │   ├── intent_classifier.py
│   │   ├── router.py
│   │   └── prompts.py
│   ├── rag/
│   │   ├── retriever.py
│   │   ├── document.py
│   │   └── vector_store.py
│   ├── tools/
│   │   ├── business_client.py
│   │   ├── package_tool.py
│   │   ├── bill_tool.py
│   │   ├── ticket_tool.py
│   │   └── user_tool.py
│   ├── memory/
│   │   ├── base.py
│   │   ├── memory_store.py
│   │   └── redis_memory.py
│   ├── safety/
│   │   └── guard.py
│   ├── auth/
│   │   └── permission.py
│   ├── observability/
│   │   ├── tracing.py
│   │   └── logger.py
│   └── utils/
│       └── time.py
├── tests/
│   └── test_chat_api.py
├── data/
│   └── mock_knowledge.md
├── requirements.txt
├── .env.example
├── README.md
└── docker-compose.yml

代码要求：
1. 使用 Pydantic v2。
2. 所有响应模型必须定义在 schemas/chat.py。
3. customer_agent.py 负责总编排，不要让 api/chat.py 写业务逻辑。
4. intent_classifier.py 输出必须包含 intent、slots、confidence。
5. router.py 根据 intent 分发到 rag 或 tools。
6. 每次 tool 调用都要记录 tool_name、input、output、success、latency_ms。
7. RAG 返回 sources，包含 doc_id、title、content、score。
8. /api/chat 出错时要返回清晰错误，不要让服务崩溃。
9. README 必须写清楚：
   - 项目定位
   - 架构说明
   - 启动方式
   - 接口示例
   - 6 类意图示例
   - 第一阶段已实现内容
   - 第二阶段扩展计划：Milvus、Redis Cluster、qwen-plus、RocketMQ、BGE Embedding、BGE Reranker、Prometheus。
10. 代码要真实可运行，不要只写伪代码。
11. 每个模块都写必要注释，注释重点解释“为什么这样设计”，方便我面试时理解。
12. 不要生成前端。
13. 不要一次性实现复杂 LangGraph、多 Agent、真实 Milvus、真实 Redis、真实 RocketMQ。第一阶段只做可运行闭环和企业级目录骨架。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 2 阶段：RAG 知识库链路

## 阶段目标

把第一阶段的 mock RAG 升级为真实可运行的知识库链路。

核心链路：

```text
知识文档
  ↓
解析清洗
  ↓
chunk 分块
  ↓
Embedding
  ↓
向量入库
  ↓
用户问题检索
  ↓
TopK 召回
  ↓
返回 sources
```

## 验收标准

1. 支持从 `data/knowledge/` 加载 Markdown / TXT 文档。
2. 支持 chunk 分块。
3. 支持本地 Chroma 作为 fallback。
4. 预留 Milvus 适配层。
5. `/api/chat` 的 `faq_query` 能返回真实 sources。
6. README 有知识库入库命令和测试示例。

## 给 Codex 的提示词

```text
请在当前第一阶段代码基础上，增量实现第二阶段：真实 RAG 知识库链路。

目标：
把当前 mock RAG 升级为真实可运行的 RAG 检索模块。该模块用于企业客服知识库问答，覆盖套餐说明、故障处理、售后规则、账单说明等文档问答。

要求：
1. 新增 data/knowledge/ 目录，放入示例知识库文档：
   - package_policy.md
   - billing_policy.md
   - fault_troubleshooting.md
   - after_sales_policy.md
2. 实现文档加载模块：
   - app/rag/loader.py
   - 支持读取 Markdown 和 TXT
   - 输出统一 Document 对象
3. 实现文本清洗模块：
   - app/rag/cleaner.py
   - 去除多余空行、异常空格、无意义符号
4. 实现 chunk 分块模块：
   - app/rag/splitter.py
   - 不要直接使用 LangChain 默认 RecursiveCharacterTextSplitter 的默认参数
   - 需要解释 keep_separator 可能导致语义边界问题
   - 使用适合中文客服文档的分块策略
   - 支持 chunk_size、chunk_overlap 参数
   - 每个 chunk 保留 source、title、chunk_id、section 等 metadata
5. 实现 embedding 抽象层：
   - app/rag/embeddings.py
   - BaseEmbedding
   - MockEmbedding
   - 可选 DashScopeEmbedding 或 OpenAICompatibleEmbedding
   - 本地默认使用 MockEmbedding，保证项目不配 API Key 也能跑
6. 实现向量库抽象层：
   - BaseVectorStore
   - ChromaVectorStore
   - MilvusVectorStore placeholder
   - 默认使用 Chroma 或 mock，后续可通过环境变量 VECTOR_STORE=chroma/milvus/mock 切换
7. 实现知识库入库脚本：
   - scripts/ingest_knowledge.py
   - 运行后可以把 data/knowledge/ 下的文档切分并写入向量库
8. 修改 app/rag/retriever.py：
   - 支持 top_k 检索
   - 返回 sources，字段包括 doc_id、title、content、score、metadata
9. 修改 faq_query 链路：
   - 当用户问业务咨询类问题时，调用真实 retriever
   - answer 中必须基于 sources 生成
   - 当前阶段可以先用模板生成答案，不强制接真实大模型
10. 增加测试：
   - tests/test_rag_ingest.py
   - tests/test_retriever.py
   - tests/test_chat_faq.py
11. README 增加：
   - 如何准备知识库
   - 如何运行 ingest 脚本
   - 如何测试 RAG 问答
   - 当前 RAG 架构说明
   - 后续 Milvus + BGE Embedding + Reranker 扩展计划

特别要求：
1. 不要破坏第一阶段 /api/chat 的已有功能。
2. faq_query 必须能返回真实 sources。
3. 出现向量库或 embedding 依赖不可用时，要 fallback 到 MockVectorStore 或关键词检索，保证项目能跑。
4. 所有新增环境变量写入 .env.example。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 3 阶段：LLM + LCEL 生成链路

## 阶段目标

接入真实大模型生成能力，把模板回答升级为 LCEL 问答链。

最终支持：

```text
retrieved_sources + user_question + conversation_context
  ↓
PromptTemplate
  ↓
qwen-plus / OpenAI-compatible LLM
  ↓
StrOutputParser
  ↓
answer
```

## 验收标准

1. 支持 qwen-plus 或 OpenAI-compatible API。
2. 支持 mock LLM fallback。
3. 使用 LCEL 写 RAG Answer Chain。
4. Prompt 中有强约束：不得编造、必须基于资料、无资料则说明无法确认。
5. temperature 默认为 0。
6. README 有大模型配置说明。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第三阶段：接入真实 LLM + LangChain LCEL 生成链路。

目标：
把当前模板式回答升级为可配置的大模型生成链路。项目技术栈要求体现 LangChain 和 LCEL。默认使用 mock LLM 保证本地可跑，配置 API Key 后可切换到 qwen-plus 或 OpenAI-compatible API。

要求：
1. 新增 app/llm/ 目录：
   - app/llm/base.py
   - app/llm/mock_llm.py
   - app/llm/qwen_llm.py
   - app/llm/factory.py
2. 支持环境变量：
   - LLM_PROVIDER=mock/qwen/openai_compatible
   - DASHSCOPE_API_KEY
   - OPENAI_API_KEY
   - OPENAI_BASE_URL
   - LLM_MODEL_NAME
   - LLM_TEMPERATURE
3. 默认使用 MockLLM，不配置 Key 也能跑。
4. 实现 RAG Answer LCEL Chain：
   - app/agents/chains/rag_answer_chain.py
   - 使用 PromptTemplate / ChatPromptTemplate
   - 使用 LCEL 管道表达式组织：prompt | llm | parser
5. RAG Prompt 必须包含企业客服约束：
   - 只能基于检索到的知识库内容回答
   - 不得编造资费、赔偿、承诺
   - 如果资料不足，要明确说“根据当前知识库无法确认”
   - 输出要简洁、专业、适合客服场景
   - 必须保留引用来源 source title
6. 修改 faq_query 链路：
   - retriever 返回 sources
   - sources 拼接进 prompt
   - LLM 生成 answer
7. 修改 fault_diagnosis 链路：
   - 先检索故障知识库
   - 再生成排查步骤
   - 必要时建议创建工单
8. 增加 hallucination guard：
   - 如果 sources 为空，不允许直接生成确定性答案
   - 返回“当前知识库未找到相关信息，建议转人工客服”
9. 增加测试：
   - tests/test_llm_factory.py
   - tests/test_rag_answer_chain.py
   - tests/test_chat_with_mock_llm.py
10. README 增加：
   - LLM_PROVIDER 配置说明
   - qwen-plus 配置说明
   - 为什么本地默认使用 mock LLM
   - LCEL 链路说明
   - 幻觉抑制策略说明

特别要求：
1. 不要在接口层直接调用 LLM，必须通过 chain 或 agent 层调用。
2. 所有 LLM 调用必须有超时、异常捕获和 fallback。
3. 默认 temperature=0。
4. 保留第一阶段和第二阶段所有已有测试通过。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 4 阶段：意图识别与多场景 Router 升级

## 阶段目标

把规则意图识别升级成企业级两阶段意图识别 Pipeline。

链路：

```text
用户问题
  ↓
规则预分类
  ↓
LLM 结构化意图识别
  ↓
输出 intent / slots / confidence
  ↓
低置信度兜底
  ↓
Router 分发到专用链路
```

## 验收标准

1. 意图识别输出结构化 JSON。
2. 支持 confidence。
3. 支持 slots 提取。
4. 低置信度自动转人工/澄清。
5. Router 可扩展。
6. 至少支持 12 类细分意图。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第四阶段：企业级意图识别与多场景 Router 升级。

目标：
把第一阶段的规则意图识别升级为“两阶段意图识别 Pipeline”：规则快速预分类 + LLM 结构化输出。最终输出 intent、slots、confidence，并根据意图路由到不同业务链路。

要求：
1. 重构 app/agents/intent_classifier.py，但不要破坏原有调用方。
2. 新增：
   - app/agents/intent_schema.py
   - app/agents/chains/intent_chain.py
3. 意图识别输出必须是结构化对象：
   - intent
   - slots
   - confidence
   - reason
4. 支持 12 类细分意图：
   - faq_query
   - package_query
   - package_recommend
   - package_change
   - bill_query
   - bill_explain
   - fault_diagnosis
   - network_repair
   - ticket_create
   - ticket_query
   - human_transfer
   - unknown
5. 第一阶段：
   - 使用规则识别做快速判断
   - 命中高确定性关键词时直接返回
6. 第二阶段：
   - 低确定性问题交给 LLM 结构化识别
   - 使用 temperature=0
   - prompt 中强制输出 JSON
7. 如果 LLM 不可用：
   - fallback 到规则分类
   - 不允许系统崩溃
8. Router 升级：
   - app/agents/router.py 支持注册式路由表
   - 不要写一堆 if else
   - 每个 intent 对应 handler
9. 增加低置信度兜底：
   - confidence < 0.6 时，返回澄清问题或转人工建议
10. slots 示例：
   - month
   - target_package
   - issue_type
   - ticket_id
   - phone_number
   - product_name
11. 增加测试：
   - tests/test_intent_classifier.py
   - tests/test_router.py
   - tests/test_low_confidence.py
12. README 增加：
   - 两阶段意图识别 Pipeline 说明
   - 12 类意图表
   - slots 设计
   - 低置信度兜底策略
   - 面试可讲点

特别要求：
1. 保留第一阶段 6 类意图兼容性。
2. 不要把 Router 写死，要体现企业级可扩展设计。
3. 输出的 intent/slots/confidence 必须进入 trace 日志。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 5 阶段：业务工具调用与 Spring Boot 边界

## 阶段目标

把 mock 工具升级为“模拟真实业务微服务调用”。

AI 服务不直接操作数据库，而是通过内部 HTTP API 调用业务服务。

推荐新增一个独立 mock 服务：

```text
mock-business-service/
  ↓
模拟 Spring Boot 业务系统
```

## 验收标准

1. AI 服务通过 httpx 调用业务服务。
2. 业务服务提供用户、套餐、账单、工单接口。
3. 业务工具层有超时、重试、异常处理。
4. tool_calls 完整记录输入、输出、耗时、成功失败。
5. README 能解释“为什么 AI 服务不直接查库”。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第五阶段：业务工具调用与 Spring Boot 业务系统边界模拟。

目标：
当前 tools 层还是本地 mock。现在需要升级为更接近企业真实架构：Python/FastAPI AI 服务不直接访问业务数据库，而是通过内部 HTTP API 调用原有 Java/Spring Boot 业务系统。为了本地可运行，本阶段请新增一个 mock-business-service，用 FastAPI 模拟 Spring Boot 业务系统接口。

要求：
1. 新增 mock_business_service/ 目录，作为独立服务：
   - mock_business_service/main.py
   - mock_business_service/schemas.py
   - mock_business_service/data.py
2. mock_business_service 提供接口：
   - GET /internal/users/{user_id}
   - GET /internal/users/{user_id}/package
   - GET /internal/users/{user_id}/bill?month=2025-04
   - POST /internal/users/{user_id}/package/change
   - POST /internal/tickets
   - GET /internal/tickets/{ticket_id}
3. app/tools/business_client.py 改为使用 httpx.AsyncClient 调用 mock_business_service。
4. 支持环境变量：
   - BUSINESS_SERVICE_BASE_URL
   - BUSINESS_SERVICE_TIMEOUT_MS
5. 所有工具调用必须有：
   - timeout
   - 异常捕获
   - success 标记
   - latency_ms
   - error_message
6. package_tool.py / bill_tool.py / ticket_tool.py / user_tool.py 都要通过 business_client 调用，不允许直接访问 mock 数据。
7. 修改 docker-compose.yml：
   - 增加 ai-service
   - 增加 mock-business-service
   - 两者在同一 network 下通信
8. 修改 /api/chat 链路：
   - package_query 调用业务服务查套餐
   - bill_query 调用业务服务查账单
   - package_change 调用业务服务办理套餐变更
   - ticket_create 调用业务服务创建工单
9. 增加业务异常场景：
   - 用户不存在
   - 账单不存在
   - 套餐不存在
   - 工单创建失败
10. 增加测试：
   - tests/test_business_client.py
   - tests/test_tools_http.py
   - tests/test_chat_business_flow.py
11. README 增加：
   - AI 服务与 Spring Boot 业务系统边界说明
   - 为什么 AI 服务不直接查业务库
   - mock-business-service 启动方式
   - docker-compose 启动方式
   - 工具调用链路图

特别要求：
1. 不要把业务数据写回 AI 服务。
2. AI 服务只能通过 business_client 访问业务能力。
3. 所有工具调用结果必须进入 tool_calls 返回字段和 trace 日志。
4. 如果 mock_business_service 不可用，AI 服务要返回友好错误，不允许崩溃。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 6 阶段：Redis 会话记忆与多轮上下文

## 阶段目标

把内存版会话升级为 RedisMemory，并实现企业级多轮对话管理。

链路：

```text
user_id + session_id
  ↓
Redis 保存最近 8 轮
  ↓
摘要压缩历史
  ↓
关键事实提取
  ↓
组装 prompt
```

## 验收标准

1. 支持 Redis 会话存储。
2. 支持内存 fallback。
3. 支持最近 8 轮上下文。
4. 支持 summary buffer。
5. 支持 key facts。
6. 支持指代消解的基础实现。
7. 会话隔离用 `user_id:session_id`。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第六阶段：Redis 会话记忆与多轮上下文管理。

目标：
把当前内存版会话记忆升级为企业级 Redis 会话记忆，支持分布式部署下的会话共享和隔离。同时实现最近 8 轮上下文、Summary Buffer、关键事实提取和基础指代消解。

要求：
1. 完善 app/memory/base.py：
   - 定义统一 MemoryStore 接口
   - append_message
   - get_recent_messages
   - get_summary
   - update_summary
   - get_key_facts
   - update_key_facts
   - clear_session
2. 完善 app/memory/redis_memory.py：
   - 使用 redis.asyncio
   - key 格式：customer_agent:{user_id}:{session_id}
   - 最近消息列表：recent_messages
   - 摘要字段：summary
   - 关键事实字段：key_facts
   - TTL 支持，默认 7 天
3. 保留 app/memory/memory_store.py 作为 InMemoryMemoryStore fallback。
4. 新增 app/memory/factory.py：
   - MEMORY_BACKEND=memory/redis
   - Redis 不可用时 fallback 到 memory，并记录 warning
5. 修改 customer_agent.py：
   - 请求开始时读取最近 8 轮上下文
   - 回答结束后写入 user message 和 assistant answer
   - 把 conversation_context 传入 RAG Answer Chain
6. 实现 Summary Buffer：
   - 当对话超过 8 轮时，把更早历史压缩成 summary
   - 默认使用 MockLLM 生成 summary
   - 真实 LLM 可用时使用真实 LLM
7. 实现关键事实提取：
   - 从对话中提取用户套餐、故障类型、已创建工单、上次查询月份等事实
   - 保存到 key_facts
8. 实现基础指代消解：
   - 当用户问“这个套餐多少钱”“它能退吗”“刚才那个工单怎么样”时，结合最近上下文和 key_facts 改写问题
   - 新增 app/agents/query_rewriter.py
9. 修改 RAG 链路：
   - 检索 query 使用改写后的 standalone_question
   - 响应中增加 rewritten_query 字段，可选
10. docker-compose.yml 增加 Redis 服务。
11. .env.example 增加：
   - MEMORY_BACKEND
   - REDIS_URL
   - MEMORY_TTL_SECONDS
   - MEMORY_RECENT_TURNS
12. 增加测试：
   - tests/test_memory_store.py
   - tests/test_redis_memory.py
   - tests/test_multi_turn_chat.py
   - tests/test_query_rewriter.py
13. README 增加：
   - 为什么不能用本地内存保存会话
   - Redis 会话隔离设计
   - Summary Buffer + 最近 8 轮策略
   - 指代消解示例
   - 多轮对话 curl 示例

特别要求：
1. Redis 不可用时，项目仍能通过内存版正常启动。
2. 不要把用户隐私敏感字段写入长期 key_facts。
3. user_id + session_id 必须共同作为会话隔离维度。
4. 每次读取和写入 memory 的耗时要进入 trace 日志。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 7 阶段：RBAC 权限控制与审计日志

## 阶段目标

让系统从 Demo 变成更像企业项目。

重点是：

```text
谁能查什么
谁能办理什么
客服代查如何审计
敏感操作如何限制
```

## 验收标准

1. role=user 只能查自己。
2. role=agent 可以代查，但必须带 target_user_id。
3. 套餐变更、账单查询、工单操作都有权限检查。
4. 敏感操作写 audit log。
5. 越权请求被拒绝。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第七阶段：RBAC 权限控制与审计日志。

目标：
把当前简单 role 判断升级为企业级 RBAC 权限体系。系统面向两类用户：C 端用户和客服人员。普通用户只能查询和操作自己的信息；客服人员可以代用户查询和创建工单，但敏感操作必须记录审计日志。

要求：
1. 扩展请求模型 ChatRequest：
   - user_id：当前登录用户
   - session_id
   - role：user/agent/admin
   - message
   - target_user_id：客服代查时使用，可选
2. 新增 app/auth/rbac.py：
   - Permission
   - Role
   - PermissionChecker
3. 定义权限：
   - FAQ_QUERY
   - PACKAGE_QUERY_SELF
   - PACKAGE_QUERY_AGENT
   - BILL_QUERY_SELF
   - BILL_QUERY_AGENT
   - PACKAGE_CHANGE_SELF
   - PACKAGE_CHANGE_AGENT
   - TICKET_CREATE_SELF
   - TICKET_CREATE_AGENT
   - TICKET_QUERY_SELF
   - TICKET_QUERY_AGENT
4. 权限规则：
   - role=user：只能访问自己的数据，target_user_id 必须为空或等于 user_id
   - role=agent：可以访问 target_user_id 的基础业务信息，但必须记录审计日志
   - role=admin：拥有全部权限
5. 新增 app/auth/context.py：
   - AuthContext
   - 包含 current_user_id、target_user_id、role、permissions
6. 修改 customer_agent.py：
   - 在进入 Router 前构造 AuthContext
   - 每个业务工具调用前必须检查权限
7. 新增 app/audit/audit_logger.py：
   - 记录客服代查、套餐变更、账单查询、工单创建等敏感操作
   - 第一版写入 logs/audit.log
   - 后续可异步写入 MQ
8. 修改 tool_calls：
   - 增加 permission_checked
   - 增加 audit_logged
9. 增加越权错误返回：
   - ForbiddenError
   - 标准错误响应
10. 增加测试：
   - tests/test_rbac_user_self.py
   - tests/test_rbac_agent_query.py
   - tests/test_rbac_forbidden.py
   - tests/test_audit_log.py
11. README 增加：
   - RBAC 权限设计
   - 普通用户和客服人员的区别
   - 为什么客服代查必须审计
   - 越权示例
   - 面试讲解点

特别要求：
1. 不要只在接口层做权限判断，业务 tool 调用前也必须检查权限。
2. 所有越权操作要有明确错误信息。
3. 审计日志中不要记录完整身份证、手机号等敏感信息，如有敏感字段必须脱敏。
4. 权限检查结果必须进入 trace 日志。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 8 阶段：内容安全防护体系

## 阶段目标

搭建企业客服场景下的全链路安全防护。

链路：

```text
用户输入
  ↓
关键词检测
  ↓
正则检测
  ↓
语义安全检测
  ↓
Agent 执行
  ↓
输出安全检测
  ↓
高危内容人工审核队列
```

## 验收标准

1. 输入输出都检测。
2. 支持风险等级。
3. 高风险直接拦截。
4. 中风险转人工。
5. 可配置安全规则。
6. 支持人工审核队列 mock。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第八阶段：全链路内容安全防护体系。

目标：
将当前最小 safety guard 升级为企业级内容安全防护体系，覆盖用户输入、工具参数、LLM 输出、高危回复人工审核。该体系用于降低违规回答、隐私泄露、错误资费承诺、诱导性操作等风险。

要求：
1. 重构 app/safety/guard.py，保留兼容入口。
2. 新增 app/safety/ 相关模块：
   - rule_engine.py
   - regex_detector.py
   - semantic_detector.py
   - risk_level.py
   - review_queue.py
   - sanitizer.py
3. 风险等级：
   - SAFE
   - LOW
   - MEDIUM
   - HIGH
   - CRITICAL
4. 检测类型：
   - sensitive_keyword：敏感词
   - privacy_leak：隐私泄露
   - price_commitment：资费/赔偿承诺
   - illegal_request：违规请求
   - prompt_injection：提示词注入
   - jailbreak：越狱诱导
   - abuse：辱骂攻击
5. 输入检测：
   - 用户 message 进入 Agent 前检查
   - HIGH/CRITICAL 直接拦截
   - MEDIUM 返回转人工建议
6. 工具参数检测：
   - 对 phone_number、user_id、target_user_id 等字段做脱敏记录
   - 不允许把敏感字段完整写入日志
7. 输出检测：
   - LLM answer 返回用户前检查
   - 如果出现“保证赔偿”“一定免费”“内部数据”等高危表述，拦截或改写
8. 规则配置：
   - 新增 config/safety_rules.yml
   - 支持关键词列表、正则规则、风险等级配置
9. SemanticDetector：
   - 当前阶段可以用 MockSemanticDetector
   - 预留 LLM 语义检测接口
10. ReviewQueue：
   - 高危内容写入 logs/review_queue.jsonl
   - 包含 trace_id、risk_type、risk_level、content_masked、created_at
11. 修改 /api/chat：
   - 返回中增加 safety_result 字段，可选
   - trace 中记录 input_safety、output_safety
12. 增加测试：
   - tests/test_safety_keywords.py
   - tests/test_safety_regex.py
   - tests/test_prompt_injection.py
   - tests/test_output_guard.py
   - tests/test_review_queue.py
13. README 增加：
   - 四级内容安全防护体系
   - 输入/输出检查流程
   - 高危内容人工审核机制
   - prompt injection 防护
   - 面试讲解点

特别要求：
1. 安全检测不能只做关键词，要有规则引擎结构，方便后续扩展。
2. 日志必须脱敏。
3. 高风险内容不允许进入 LLM。
4. 输出内容返回用户前必须二次检查。
5. 所有 safety 检测结果必须进入 trace 日志。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 9 阶段：RocketMQ 异步解耦

## 阶段目标

用 MQ 体现企业级系统解耦能力。

适合异步化的事件：

1. 工单创建后通知
2. 审计日志写入
3. AI 评测记录落库
4. 高危内容人工审核
5. 用户满意度回传

## 验收标准

1. 有统一事件模型。
2. 有 MQ Producer 抽象。
3. 默认 mock producer。
4. 预留 RocketMQProducer。
5. 工单/审计/评测事件可以异步发送。
6. MQ 不可用不影响主问答链路。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第九阶段：RocketMQ 异步解耦与事件机制。

目标：
将部分非主链路操作从同步调用中解耦，体现企业级 AI 客服系统中的异步事件架构。第一版默认使用 MockEventProducer 保证本地可运行，同时预留 RocketMQProducer，后续可切换真实 RocketMQ。

适合异步化的场景：
1. 工单创建后的通知事件
2. 客服代查审计日志事件
3. AI 问答质量评测记录事件
4. 高危内容人工审核事件
5. 用户满意度回传事件

要求：
1. 新增 app/events/ 目录：
   - event_schema.py
   - event_type.py
   - producer.py
   - mock_producer.py
   - rocketmq_producer.py
   - event_bus.py
2. 定义统一事件模型：
   - event_id
   - event_type
   - trace_id
   - user_id
   - session_id
   - payload
   - created_at
3. 支持事件类型：
   - TICKET_CREATED
   - AUDIT_LOG_CREATED
   - AI_QA_FINISHED
   - SAFETY_REVIEW_REQUIRED
   - USER_FEEDBACK_CREATED
4. 默认使用 MockEventProducer：
   - 写入 logs/events.jsonl
5. RocketMQProducer：
   - 当前阶段可以实现 placeholder
   - 结构上体现 topic、tag、message_key、payload
   - 不强制真实连接 RocketMQ
6. 支持环境变量：
   - EVENT_PRODUCER=mock/rocketmq/none
   - ROCKETMQ_NAME_SERVER
   - ROCKETMQ_TOPIC
7. 修改工单创建链路：
   - create_ticket 成功后发送 TICKET_CREATED 事件
8. 修改审计链路：
   - audit log 可以同步写本地，同时发送 AUDIT_LOG_CREATED 事件
9. 修改问答结束链路：
   - 每次 /api/chat 完成后发送 AI_QA_FINISHED 事件
   - payload 包含 intent、latency_ms、tool_count、source_count、safety_risk_level
10. 修改内容安全链路：
   - 高危内容进入 review_queue 时，发送 SAFETY_REVIEW_REQUIRED 事件
11. MQ 失败处理：
   - 事件发送失败不能影响主问答链路
   - 必须记录 warning 日志
12. 增加测试：
   - tests/test_event_schema.py
   - tests/test_mock_event_producer.py
   - tests/test_chat_event_flow.py
13. README 增加：
   - 为什么需要 RocketMQ 异步解耦
   - 哪些事件适合异步化
   - 主链路和异步链路边界
   - RocketMQ 后续接入方式
   - 面试讲解点

特别要求：
1. 不要为了 MQ 改坏主流程。
2. 事件发送失败不能导致 /api/chat 失败。
3. 所有事件必须带 trace_id，方便后续追踪。
4. 默认本地模式必须不依赖真实 RocketMQ。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 10 阶段：可观测性与 AI 评测体系

## 阶段目标

实现简历里最重要的企业级亮点之一：

```text
trace_id + intent + slots + sources + tool_calls + latency + token_cost + safety
```

同时构建离线评测集：

```text
准确率
召回率
幻觉率
响应时延
Token 成本
工具调用准确率
```

## 验收标准

1. 每轮对话有完整 trace。
2. 支持 trace 回放。
3. 支持评测数据集。
4. 支持运行评测脚本。
5. 输出评测报告 JSON/Markdown。
6. README 能解释评测指标。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第十阶段：全链路可观测性与 AI 效果评测体系。

目标：
构建企业级 AI 客服系统的可观测性与评测体系。每次问答都能通过 trace_id 回放完整执行过程，包括意图识别、RAG 检索、工具调用、LLM 生成、内容安全、耗时与成本。并提供离线评测脚本，用于量化准确率、幻觉率、响应时延和工具调用准确率。

要求一：可观测性增强
1. 完善 app/observability/tracing.py：
   - TraceContext
   - TraceSpan
   - start_span
   - end_span
   - add_event
   - add_attribute
2. 使用 ContextVar 保存当前 trace_id 和 trace_context。
3. 每次 /api/chat 必须记录以下字段：
   - trace_id
   - user_id_masked
   - session_id
   - role
   - intent
   - slots
   - confidence
   - rewritten_query
   - retrieved_sources
   - tool_calls
   - input_safety
   - output_safety
   - llm_provider
   - model_name
   - prompt_tokens
   - completion_tokens
   - total_tokens
   - latency_ms
   - error
4. 新增 app/observability/trace_repository.py：
   - 第一版写入 logs/traces/{trace_id}.json
5. 新增接口：
   - GET /api/traces/{trace_id}
   - 用于本地演示 trace 回放
6. 新增 app/observability/callbacks.py：
   - 自定义 CallbackHandler placeholder
   - 用于后续接 LangChain callback
7. 所有日志必须脱敏。

要求二：AI 评测体系
1. 新增 evals/ 目录：
   - evals/datasets/customer_qa_eval.jsonl
   - evals/run_eval.py
   - evals/metrics.py
   - evals/report.py
2. 评测数据每条包含：
   - question
   - expected_intent
   - expected_keywords
   - expected_tool
   - should_have_sources
   - risk_case
3. 实现指标：
   - intent_accuracy
   - tool_call_accuracy
   - source_recall_rate
   - hallucination_rate 简化版
   - avg_latency_ms
   - safety_block_rate
4. evals/run_eval.py 可以批量调用本地 /api/chat。
5. 输出：
   - evals/reports/latest_report.json
   - evals/reports/latest_report.md
6. README 增加：
   - trace_id 设计
   - 为什么需要完整链路回放
   - AI 评测指标说明
   - 如何运行评测
   - 如何解读报告
   - 面试讲解点

特别要求：
1. trace 不要只记录日志，要能通过 GET /api/traces/{trace_id} 查询。
2. 评测脚本必须可以真实运行。
3. 如果 token 统计暂时拿不到真实值，可以先用估算方法，并在代码注释说明后续如何接真实模型 usage。
4. 不要泄露完整用户隐私字段。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 11 阶段：性能优化与部署

## 阶段目标

让项目具备“企业级部署感”。

包括：

1. Docker Compose
2. Redis
3. mock business service
4. 可选 Milvus
5. 健康检查
6. 压测脚本
7. 连接池
8. 超时与降级

## 验收标准

1. `docker compose up -d` 可启动核心服务。
2. `/health` 和 `/ready` 可用。
3. 提供压测脚本。
4. 有超时、重试、降级。
5. README 有部署说明。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第十一阶段：性能优化、稳定性保障与 Docker Compose 部署。

目标：
让当前项目从“可运行 Demo”升级为“具备企业级部署感的面试项目”。重点实现健康检查、服务依赖检查、连接池、超时控制、降级策略、Docker Compose、本地压测脚本。

要求一：健康检查
1. 新增接口：
   - GET /health：服务存活检查
   - GET /ready：依赖就绪检查
2. /ready 检查：
   - memory backend
   - business service
   - vector store
   - event producer
   - llm provider
3. 返回结构化结果。

要求二：稳定性增强
1. business_client 增加：
   - httpx 连接池
   - timeout
   - retry
   - circuit breaker 简化版
2. LLM 调用增加：
   - timeout
   - fallback
   - retry 可配置
3. vector store 调用增加：
   - timeout
   - fallback 到关键词检索
4. Redis 不可用时 fallback 到 memory。
5. MQ 不可用时 fallback 到 local jsonl event log。

要求三：Docker Compose
1. 完善 docker-compose.yml：
   - ai-service
   - mock-business-service
   - redis
   - 可选 chroma 或 milvus profile
2. 增加 Dockerfile：
   - ai-service/Dockerfile 或根目录 Dockerfile
   - mock_business_service/Dockerfile
3. .env.example 完善所有环境变量。
4. README 增加 docker compose 启动方式。

要求四：压测脚本
1. 新增 scripts/load_test.py：
   - 并发请求 /api/chat
   - 参数：concurrency、total_requests、scenario
   - 输出 avg_latency、p95、p99、success_rate
2. 新增 scripts/scenarios/：
   - faq.json
   - bill_query.json
   - package_query.json
   - fault_diagnosis.json
3. 输出 reports/load_test_report.json。

要求五：性能优化点
1. 对知识库检索结果增加简单缓存：
   - query hash -> sources
   - TTL 可配置
2. 对用户套餐/账单查询增加短 TTL 缓存：
   - 注意套餐变更后要失效
3. trace 中记录 cache_hit。

增加测试：
1. tests/test_health.py
2. tests/test_ready.py
3. tests/test_fallback.py
4. tests/test_cache.py

README 增加：
1. Docker Compose 部署方式
2. 健康检查说明
3. 降级策略说明
4. 压测脚本使用方式
5. 面试讲解点：如何保障高并发和稳定性

特别要求：
1. 本地 16GB 内存也要能跑核心服务，所以 Milvus 放到 optional profile，不要默认强制启动。
2. 核心链路必须在 mock/chroma/redis 模式下轻量启动。
3. 不要为了部署复杂度牺牲本地可运行性。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 12 阶段：面试交付材料

## 阶段目标

把项目整理成面试官能看懂、你自己能讲清楚的交付物。

最终交付：

1. README
2. 架构说明
3. 核心链路图
4. 业务案例
5. 面试讲解稿
6. 常见追问回答
7. 项目启动脚本
8. 测试脚本
9. Demo 演示脚本

## 验收标准

1. README 不只是启动说明，而是项目说明书。
2. 有面试讲解材料。
3. 有 5 个真实业务案例。
4. 有常见八股追问答案。
5. 能按脚本完成演示。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第十二阶段：面试交付材料整理。

目标：
把当前企业级 AI 客服问答系统 Demo 整理成可用于 Agent 开发岗位面试展示的完整交付物。重点不是继续堆功能，而是让项目架构、业务链路、技术亮点、启动方式、演示案例、面试话术都清晰可讲。

要求一：README 升级
请重写 README.md，但不要夸大项目功能。README 需要包含：
1. 项目定位
2. 背景痛点
3. 总体架构
4. 技术栈
5. 目录结构
6. 核心链路
7. 业务场景
8. RAG 链路说明
9. 意图识别与 Router 说明
10. 工具调用与 Spring Boot 边界说明
11. Redis 多轮会话说明
12. RBAC 权限说明
13. 内容安全说明
14. RocketMQ 异步事件说明
15. 可观测性与评测说明
16. Docker 启动方式
17. 本地开发启动方式
18. API 文档
19. curl 示例
20. 测试与评测方式
21. 项目阶段说明
22. 后续可扩展方向

要求二：新增 docs/ 文档
新增 docs/ 目录：
1. docs/architecture.md
2. docs/rag_design.md
3. docs/agent_router_design.md
4. docs/memory_design.md
5. docs/security_design.md
6. docs/observability_design.md
7. docs/interview_guide.md
8. docs/demo_script.md

要求三：interview_guide.md
必须包含：
1. 30 秒项目介绍
2. 2 分钟项目介绍
3. 5 分钟详细讲解
4. 项目架构怎么讲
5. RAG 优化怎么讲
6. 意图识别怎么讲
7. 多轮对话怎么讲
8. 工具调用怎么讲
9. 权限安全怎么讲
10. 可观测性怎么讲
11. 性能优化怎么讲
12. 项目难点怎么讲
13. 面试官追问与参考回答

要求四：demo_script.md
必须包含 5 个演示案例：
1. 用户咨询套餐规则
2. 用户查询当前套餐
3. 用户查询账单异常
4. 用户故障排查并创建工单
5. 客服人员代用户查询账单并记录审计日志

每个案例包含：
- curl 请求
- 预期响应字段
- 这条链路经过哪些模块
- 面试时怎么解释

要求五：架构图
不要生成图片。使用 Mermaid 或 ASCII 图写在 markdown 里：
1. 总体架构图
2. /api/chat 主链路图
3. RAG 检索生成链路图
4. 工具调用链路图
5. 可观测性链路图

要求六：启动脚本
新增：
1. scripts/dev_start.sh
2. scripts/dev_start.ps1
3. scripts/run_tests.sh
4. scripts/run_eval.sh

要求七：最终自检
新增 docs/checklist.md：
包含：
1. 项目能否启动
2. API 能否调用
3. RAG 是否有 sources
4. 工具调用是否有 tool_calls
5. trace 是否可查询
6. Redis 不可用是否 fallback
7. LLM 不可用是否 fallback
8. MQ 不可用是否 fallback
9. 测试是否通过
10. README 是否完整

特别要求：
1. 文档必须符合真实项目，不要写“本项目已经支撑 5 万并发”这种无法证明的夸张内容。
2. 可以写“生产环境可扩展为 Redis Cluster / Milvus / RocketMQ / Prometheus”，但当前 Demo 实现什么就写什么。
3. 面试材料要贴合 Agent 开发岗位，不要写成普通 Java 后端项目。
4. 所有文档都要帮助我讲清楚：为什么这是企业级 AI 客服中台，不是普通 ChatBot。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 13 阶段：简历成果映射与真实接入路线图

## 阶段目标

把简历中的生产项目经历和当前仓库逐项映射，明确当前仓库已经实现什么、哪些仍是 mock/fallback/placeholder、哪些需要在第 14-18 阶段真实接入。

本阶段不改业务主链路，不新增环境变量，不生成前端页面。重点是建立后续真实接入路线图，避免后续开发偏离简历内容。

## 验收标准

1. 新增 `docs/resume_mapping.md`。
2. README 增加简历映射入口，但不失控变长。
3. interview_guide 能解释生产项目与当前仓库差异。
4. demo_script 能说明现场演示能力和后续真实接入能力。
5. checklist 增加简历映射自检。
6. pytest 能检查文档存在、章节完整和禁止夸大表述。

## 给 Codex 的提示词

```text
请在当前代码基础上，增量实现第十三阶段：简历成果映射与真实接入路线图。

目标：
不是只做 Demo 边界说明，而是把我的简历生产项目能力和当前仓库逐项对齐，并明确第 14-18 阶段如何真实接入 Milvus、BGE、Reranker、RocketMQ、Offer/Order 和 Prometheus-compatible metrics。

要求一：新增 docs/resume_mapping.md
必须包含：
1. 简历项目概述
2. 当前仓库与简历能力总览
3. 技术栈映射表
4. 核心职责映射表
5. 成果指标映射表
6. 当前已实现能力
7. 当前 mock / fallback / placeholder 能力
8. 需要真实接入的能力清单
9. 当前仓库与真实生产项目差距
10. 面试讲解口径
11. 禁止夸大说明
12. 第 14-18 阶段真实接入路线图

要求二：更新现有文档
1. README 增加简历映射入口。
2. docs/interview_guide.md 增加“如何解释生产项目与当前仓库差异”。
3. docs/demo_script.md 增加“演示能力与真实接入边界”。
4. docs/checklist.md 增加“简历映射自检”。
5. docs/codex_phase_prompts.md 追加第 13-18 阶段规划。

要求三：测试
补充 pytest 文档测试：
1. 验证 docs/resume_mapping.md 存在且章节完整。
2. 验证 README、interview_guide、demo_script、checklist 有简历映射入口。
3. 验证文档不会把当前仓库描述成已经连接真实 Milvus、RocketMQ、Redis Cluster、Prometheus/Grafana 或支持生产级高并发。
4. 验证第 14-18 阶段真实接入路线存在。

特别要求：
1. 本阶段原则上不改 app/ 业务代码。
2. 不新增环境变量。
3. 不生成前端页面。
4. 文档中必须体现“真实接入优先，fallback 保底”。
5. 不能把生产项目指标写成当前本地仓库自动化测试结果。

通用开发约束：
1. 必须基于当前已有代码增量开发，不要推翻重写整个项目。
2. 不要把业务逻辑写到 main.py 或 api 层，必须保持分层清晰。
3. 每个新增模块必须有必要注释，注释重点解释“为什么这样设计”。
4. 每个阶段完成后必须更新 README 的“当前阶段能力”和“启动方式”。
5. 每个阶段必须提供至少 3 个可运行 curl 示例。
6. 每个阶段必须补充或更新 pytest 测试。
7. 代码必须真实可运行，不要写伪代码。
8. 出现外部依赖时，必须提供 mock/fallback 模式，保证本地最小版本仍能启动。
9. 如果需要新增环境变量，必须同步更新 .env.example。
10. 不要生成前端。
```

---

# 第 14 阶段：RAG 真实检索增强

## 阶段目标

把当前基础 RAG 链路升级为更贴近简历生产项目的检索链路：零宽断言句末分块、MMR 多样性召回、BGE Embedding provider、Reranker 抽象和 Milvus 真实适配。

## 验收标准

1. `app/rag/splitter.py` 支持零宽断言句末分块，并保留 section metadata。
2. `app/rag/vector_store.py` 提供可配置的真实 Milvus 适配，Milvus 不可用时 fallback。
3. 新增 MMR 检索或重排工具函数。
4. 新增 Reranker 抽象，默认 mock，可配置 BGE-Reranker。
5. trace 中记录 candidate_count、top_k、reranker_used、vector_store_type。
6. README 和 resume_mapping 同步说明真实接入进度。

---

# 第 15 阶段：AI 评测体系增强

## 阶段目标

把第 10 阶段的基础 eval 扩展为更贴近简历指标的评测体系，覆盖 Top1/Top3/TopK、召回覆盖、幻觉、意图、工具、安全、延迟和 Token 成本。

## 验收标准

1. eval dataset 支持 expected_sources、expected_top_k、expected_rerank。
2. metrics 支持 Top1、Top3、TopK、source coverage、hallucination、intent、tool、safety、latency、token cost。
3. report 输出 JSON 和 Markdown，并区分本地评测指标与生产项目指标。
4. README 和 resume_mapping 同步更新评测口径。

---

# 第 16 阶段：Offer / Order 业务域增强

## 阶段目标

补齐简历中的商品 offer、订单 order 基础业务模块。AI 服务仍通过 BusinessClient 调用业务系统 API，不直接访问 MySQL。

## 验收标准

1. mock_business_service 新增 offer/order 内部 API。
2. app/tools 新增 OfferTool、OrderTool 或同等边界。
3. Router 增加 offer_query、offer_recommend、order_query 等必要意图。
4. RBAC、审计、tool safety、tool_calls 和 trace 完整覆盖新增业务域。
5. README、demo_script、resume_mapping 同步新增业务案例。

---

# 第 17 阶段：性能与可观测性增强

## 阶段目标

增强本地可观测性和性能报告能力，为真实监控平台接入做准备，但不默认依赖 Prometheus/Grafana/OTel Collector。

## 验收标准

1. 新增 Prometheus-compatible `/metrics` 文本接口。
2. trace 中补齐关键 latency 字段，包括 intent、rag、llm、tool、memory、event。
3. simple_load_test 输出性能报告 JSON/Markdown。
4. README 和 interview_guide 说明本地压测不是生产容量承诺。

---

# 第 18 阶段：最终面试演示闭环

## 阶段目标

把第 1-17 阶段整理成最终面试交付包：代码、文档、演示脚本、评测报告、压测报告和简历口径完全一致。

## 验收标准

1. README、resume_mapping、interview_guide、demo_script、checklist 完全同步。
2. 至少 5 个核心 curl 案例覆盖 RAG、Tools、Memory、RBAC、安全、事件和 trace。
3. eval 和 load report 可生成并被文档引用。
4. pytest、smoke_test、eval、demo_check 均可运行。
5. 文档能清楚区分生产项目真实能力、当前仓库已实现能力和本地 fallback 边界。

---

## 四、推荐执行顺序

严格按顺序执行：

```text
第 1 阶段：先跑通主链路
第 2 阶段：补 RAG
第 3 阶段：补 LLM + LCEL
第 4 阶段：补意图识别和 Router
第 5 阶段：补业务系统 HTTP 工具调用
第 6 阶段：补 Redis 多轮会话
第 7 阶段：补 RBAC 权限
第 8 阶段：补内容安全
第 9 阶段：补 RocketMQ 事件
第 10 阶段：补 trace 和评测
第 11 阶段：补部署、健康检查、压测
第 12 阶段：补面试文档和演示脚本
第 13 阶段：补简历成果映射和真实接入路线图
第 14 阶段：补 RAG 真实检索增强
第 15 阶段：补 AI 评测体系增强
第 16 阶段：补 Offer / Order 业务域
第 17 阶段：补性能与可观测性增强
第 18 阶段：补最终面试演示闭环
```

不要跳阶段。每个阶段完成后先做三件事：

```bash
pytest
uvicorn app.main:app --reload
curl 测试核心接口
```

通过后再进入下一阶段。

---

## 五、每阶段完成后的复盘问题

每个阶段完成后，你都要能回答这 5 个问题：

1. 这个阶段解决了什么业务问题？
2. 为什么企业项目需要这个模块？
3. 这个模块在代码里从哪里入口？
4. 如果面试官问生产环境怎么做，你怎么回答？
5. 当前 Demo 和真实生产环境还有什么差距？

---

## 六、最终面试讲法

这个项目最终要这样讲：

```text
这个项目不是单纯 ChatBot，而是在原有 Spring Boot 业务系统旁边新增 Python/FastAPI AI 服务层，形成“业务微服务 + AI 服务层”的融合架构。

用户请求进入 AI 服务后，会先经过权限校验和内容安全检查，再做意图识别和 Router 分发。如果是知识问答类问题，会进入 RAG 检索链路；如果是套餐、账单、工单等业务操作，会通过工具调用访问原有业务系统 API。

系统通过 Redis 管理多轮会话，解决多实例部署下的上下文共享和会话隔离问题；通过 trace_id、结构化日志和评测脚本记录完整 Agent 执行过程，方便线上问题复盘和效果优化。

所以它的核心价值不是“让大模型回答问题”，而是把大模型、RAG、工具调用、权限、安全、观测这些能力工程化地接入真实业务系统。
```
