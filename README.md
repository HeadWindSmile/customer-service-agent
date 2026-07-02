# 企业级 AI 客服问答系统 Demo

## 项目定位

本项目用于 Agent 开发岗位面试展示。它不是普通 ChatBot，而是在原有 Java/Spring Boot 主业务系统旁边新增一层 Python/FastAPI AI 服务，模拟“业务微服务 + AI 服务层（LLM + Agent）”融合架构。

## 当前阶段能力

当前处于第 6 阶段：Redis 会话记忆与多轮上下文。

已实现：

1. `POST /api/chat` 接口。
2. 两阶段意图识别 Pipeline：规则预分类 + LLM 结构化 JSON 识别。
3. 支持 12 类细分意图：`faq_query`、`package_query`、`package_recommend`、`package_change`、`bill_query`、`bill_explain`、`fault_diagnosis`、`network_repair`、`ticket_create`、`ticket_query`、`human_transfer`、`unknown`。
4. 意图识别结果包含 `intent`、`slots`、`confidence`、`reason`，并进入 trace 日志。
5. Router 升级为注册式路由表，新增意图只需注册 handler。
6. 低置信度兜底：`confidence < 0.6` 时返回澄清问题，不调用 RAG 或业务工具。
7. Router 分发机制：FAQ、账单解释、套餐推荐和故障排查走真实知识库检索；套餐、账单、工单走业务工具。
8. 新增独立 `mock_business_service/`，用 FastAPI 模拟原有 Spring Boot 业务系统内部 HTTP API。
9. AI 服务通过 `BusinessClient` 抽象访问业务能力，支持 `HttpBusinessClient` 和本地 `MockBusinessClient` fallback。
10. 业务工具调用支持 timeout、业务异常、服务不可用降级，并在 `tool_calls` 中记录 `tool_name`、`input`、`output`、`success`、`latency_ms`、`error_message`。
11. 会话记忆升级为 `MemoryStore` 抽象，支持 Redis 存储和内存 fallback，按 `user_id + session_id` 隔离。
12. 最小 RBAC：普通用户只能查自己，客服可代查并输出审计日志。
13. 最小内容安全：输入敏感词检查、输出高危承诺检查。
14. 结构化响应：`answer`、`intent`、`slots`、`confidence`、`intent_reason`、`sources`、`tool_calls`、`trace_id`、`latency_ms`。
15. 结构化 JSON 日志和轻量 trace。
16. 从 `data/knowledge/` 加载 Markdown/TXT，完成清洗、分块、MockEmbedding、向量检索和 sources 引用。
17. 使用 LangChain LCEL 实现 RAG Answer Chain：`Prompt -> LLM -> StrOutputParser`。
18. 默认 `MockLLM`，不配置 API Key 也能跑通问答链路。
19. 可通过 OpenAI-compatible API 接入 `qwen-plus` 或其他兼容模型。
20. sources 为空时直接兜底转人工，不允许 LLM 编造答案。
21. 最近 8 轮上下文会进入 RAG Prompt，超过窗口的早期历史会压缩进 Summary Buffer。
22. 支持 `key_facts`，用于保存当前套餐、最近账单月份、最近工单号等安全业务事实。
23. 支持基础指代消解，响应中返回可选 `rewritten_query`，RAG 检索使用改写后的独立问题。
24. memory 读写耗时、backend、summary/key_facts 状态进入结构化 trace 日志。

## 架构说明

```text
POST /api/chat
  -> api/chat.py 参数校验
  -> customer_agent.py 主编排
  -> permission.py 权限校验
  -> guard.py 输入安全检查
  -> intent_classifier.py 规则预分类
  -> intent_chain.py LLM 结构化意图识别
  -> confidence 低置信度兜底
  -> router.py 注册式路由分发
  -> RAG retriever + LCEL answer chain / business tools
  -> BusinessClient
  -> mock_business_service 内部 HTTP API（模拟 Spring Boot）
  -> qwen-plus/OpenAI-compatible LLM 或 MockLLM fallback
  -> guard.py 输出安全检查
  -> tracing.py + logger.py 记录 trace
  -> 返回结构化结果
```

## 启动方式

最小本地模式只启动 AI 服务。此时 `BUSINESS_SERVICE_BASE_URL` 为空，业务工具会使用本地 `MockBusinessClient` fallback：

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认 `MEMORY_BACKEND=memory`，不依赖 Redis 也可以启动。需要使用 Redis 会话记忆时：

```bash
$env:MEMORY_BACKEND="redis"
$env:REDIS_URL="redis://localhost:6379/0"
$env:MEMORY_TTL_SECONDS="604800"
$env:MEMORY_RECENT_TURNS="8"
uvicorn app.main:app --reload
```

如果 Redis 不可用，系统会自动降级到内存版会话，保证本地最小版本可运行。

第 5 阶段推荐启动两个服务，模拟“Python/FastAPI AI 服务 + Java/Spring Boot 业务系统”：

```bash
uvicorn mock_business_service.main:app --host 127.0.0.1 --port 8010
```

另开一个终端：

```bash
$env:BUSINESS_SERVICE_BASE_URL="http://127.0.0.1:8010"
$env:BUSINESS_SERVICE_TIMEOUT_MS="800"
uvicorn app.main:app --reload
```

Docker Compose 启动：

```bash
docker compose up -d
docker compose ps
```

Docker Compose 会同时启动 `ai-service`、`mock-business-service` 和 `redis`。

接口文档：

```text
http://127.0.0.1:8000/docs
```

mock 业务服务文档：

```text
http://127.0.0.1:8010/docs
```

## 测试方式

```bash
pytest
```

## AI 服务与业务系统边界

本项目模拟企业里常见的“原有 Spring Boot 主业务系统 + 新增 Python AI 服务层”架构。用户、套餐、账单、工单属于主业务系统的数据和事务边界，AI 服务不直接查业务库，也不直接写业务表。

这样设计有三个原因：

1. 权限、审计、事务一致性仍由主业务系统负责。
2. AI 服务只编排问答和工具调用，避免绕过已有业务规则。
3. 未来从 mock 服务替换为真实 Spring Boot 服务时，只需要替换 `BUSINESS_SERVICE_BASE_URL` 和内部接口实现。

业务工具调用链路：

```text
Router
  -> PackageTool / BillTool / TicketTool / UserTool
  -> BusinessClient 抽象
  -> HttpBusinessClient
  -> mock_business_service /internal/* API
```

本地 fallback 链路：

```text
Router
  -> tools
  -> MockBusinessClient
```

当 `BUSINESS_SERVICE_BASE_URL` 为空时走 fallback；当配置该变量时，AI 服务通过 `httpx.AsyncClient` 调用业务服务。HTTP 超时、连接失败、4xx/5xx 业务错误都会被记录到 `tool_calls`，主链路返回友好失败文案，不会让接口崩溃。

业务服务配置：

```bash
BUSINESS_SERVICE_BASE_URL=http://127.0.0.1:8010
BUSINESS_SERVICE_TIMEOUT_MS=800
```

## Redis 会话记忆与多轮上下文

第 6 阶段把原来的进程内最近 8 轮记忆升级为统一 `MemoryStore` 抽象：

```text
CustomerAgent
  -> ConversationMemoryManager
  -> MemoryStore
     -> RedisMemory
     -> InMemoryMemoryStore fallback
```

为什么不能只用本地内存：

1. 多实例部署时，同一用户的下一轮请求可能落到另一台实例，进程内存无法共享。
2. 服务重启后上下文会丢失，不利于客服多轮对话体验。
3. 只用 `session_id` 容易串话，第 6 阶段改为 `user_id + session_id` 共同隔离。

Redis key 设计：

```text
customer_agent:{user_id}:{session_id}:recent_messages
customer_agent:{user_id}:{session_id}:summary
customer_agent:{user_id}:{session_id}:key_facts
```

上下文策略：

1. 最近 8 轮保留为原始短期上下文。
2. 超过 8 轮后，更早历史压缩到 summary buffer。
3. `key_facts` 只保存白名单业务事实，例如当前套餐、最近账单月份、最近工单号，不保存手机号、身份证、银行卡等隐私字段。
4. query rewriter 使用 recent turns + key_facts 做基础指代消解，例如把“这个套餐什么时候生效”改写成“5G畅享套餐什么时候生效”。
5. RAG 检索使用 `rewritten_query`，响应中也返回该字段，便于演示和排查。

会话记忆配置：

```bash
MEMORY_BACKEND=memory
REDIS_URL=redis://localhost:6379/0
MEMORY_TTL_SECONDS=604800
MEMORY_RECENT_TURNS=8
```

## 知识库入库

示例知识库位于：

```text
data/knowledge/
├── package_policy.md
├── billing_policy.md
├── fault_troubleshooting.md
└── after_sales_policy.md
```

执行入库：

```bash
python scripts/ingest_knowledge.py
```

默认使用 `MockEmbedding` 和本地 mock vector store，索引写入 `data/vector_store/`。该目录是运行时产物，不需要提交。

## 大模型配置

默认本地模式不需要配置任何 Key：

```bash
LLM_PROVIDER=mock
```

接入 qwen-plus：

```bash
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=你的 DashScope Key
LLM_MODEL_NAME=qwen-plus
LLM_TEMPERATURE=0
```

接入阿里云百炼上的其他 OpenAI-compatible 模型，例如 deepseek-v4-flash：

```bash
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=你的 DashScope Key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=deepseek-v4-flash
LLM_TEMPERATURE=0
```

接入 OpenAI-compatible API：

```bash
LLM_PROVIDER=openai_compatible
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=https://your-compatible-endpoint/v1
LLM_MODEL_NAME=你的模型名称
LLM_TEMPERATURE=0
```

如果 Key 缺失、依赖不可用或真实模型调用异常，系统会 fallback 到 `MockLLM`，保证本地最小版本仍能启动和测试。

意图识别阈值配置：

```bash
INTENT_RULE_DIRECT_THRESHOLD=0.85
INTENT_LOW_CONFIDENCE_THRESHOLD=0.6
```

规则预分类命中高确定性关键词且置信度达到 `INTENT_RULE_DIRECT_THRESHOLD` 时直接返回；低确定性问题进入 LLM 结构化识别。最终 `confidence < INTENT_LOW_CONFIDENCE_THRESHOLD` 时，系统返回澄清问题或转人工建议，不触发工具调用。

真实向量模型配置：

```bash
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL_NAME=text-embedding-v4
EMBEDDING_DIMENSIONS=768
EMBEDDING_TIMEOUT_SECONDS=10
```

`text-embedding-v4` 支持多种向量维度。本项目默认建议使用 768 维，在客服知识库 Demo 中兼顾检索效果和本地索引体积。

## 当前 RAG 架构

```text
data/knowledge/*.md 或 *.txt
  -> loader.py 读取文档
  -> cleaner.py 清洗文本
  -> splitter.py 中文客服文档分块
  -> embeddings.py 生成 mock embedding
  -> vector_store.py 写入 mock/chroma store
  -> retriever.py top_k 检索
  -> rag_answer_chain.py 使用 LCEL 生成 answer
  -> /api/chat 返回 answer + sources
```

第 3 阶段的 LCEL 链路：

```text
retrieved_sources + user_question + conversation_context
  -> ChatPromptTemplate
  -> qwen-plus / OpenAI-compatible LLM / MockLLM
  -> StrOutputParser
  -> answer
```

Prompt 中强约束：只能基于检索资料回答，不得编造资费、赔偿或办理承诺；如果资料不足，必须说明无法确认并建议转人工客服。代码层也会在 `sources` 为空时直接返回兜底文案，不进入 LLM。

## curl 示例

第 5 阶段业务工具调用示例：

套餐查询：

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase5-s1\",\"role\":\"user\",\"message\":\"查询我的当前套餐\"}"
```

账单查询：

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase5-s2\",\"role\":\"user\",\"message\":\"帮我查本月账单\"}"
```

工单创建：

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase5-s3\",\"role\":\"user\",\"message\":\"我要创建工单，宽带断网\"}"
```

第 6 阶段多轮对话示例：

套餐指代消解：

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase6-package\",\"role\":\"user\",\"message\":\"查询我的当前套餐\"}"

curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase6-package\",\"role\":\"user\",\"message\":\"这个套餐什么时候生效？\"}"
```

工单指代消解：

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase6-ticket\",\"role\":\"user\",\"message\":\"我要创建工单，宽带断网\"}"

curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase6-ticket\",\"role\":\"user\",\"message\":\"刚才那个工单进度怎么样？\"}"
```

账单指代消解：

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase6-bill\",\"role\":\"user\",\"message\":\"帮我查本月账单\"}"

curl.exe -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase6-bill\",\"role\":\"user\",\"message\":\"这笔费用为什么会有超量流量费？\"}"
```

FAQ 查询：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"s1\",\"role\":\"user\",\"message\":\"套餐变更什么时候生效？\"}"
```

账单解释：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"user_001\",\"session_id\":\"rag-s2\",\"role\":\"user\",\"message\":\"账单里为什么会有超量流量费用？\"}"
```

故障排查：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"user_001\",\"session_id\":\"rag-s3\",\"role\":\"user\",\"message\":\"宽带连不上应该怎么排查？\"}"
```

套餐查询：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"s1\",\"role\":\"user\",\"message\":\"查询我的当前套餐\"}"
```

账单查询：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"s1\",\"role\":\"user\",\"message\":\"帮我查本月账单\"}"
```

工单创建：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"s1\",\"role\":\"user\",\"message\":\"我要创建工单，宽带断网\"}"
```

套餐推荐：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase4-s1\",\"role\":\"user\",\"message\":\"我流量经常不够，推荐一个适合的套餐\"}"
```

工单查询：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase4-s2\",\"role\":\"user\",\"message\":\"帮我查工单 TCK-ABC123456 的进度\"}"
```

低置信度兜底：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"phase4-s3\",\"role\":\"user\",\"message\":\"随便看看这个事情\"}"
```

## 12 类意图示例

| 意图 | 示例问题 | 当前链路 |
|---|---|---|
| `faq_query` | 套餐变更什么时候生效？ | 真实知识库检索 |
| `package_query` | 查询我的当前套餐 | mock 业务工具 |
| `package_recommend` | 我流量经常不够，推荐一个适合的套餐 | 真实知识库检索 + 保守建议 |
| `package_change` | 我要办理5G畅享套餐 | mock 业务工具 |
| `bill_query` | 帮我查本月账单 | mock 业务工具 |
| `bill_explain` | 账单里为什么会有超量流量费用？ | 真实知识库检索 |
| `fault_diagnosis` | 宽带不能上网怎么办？ | 真实知识库检索 + 工单建议 |
| `network_repair` | 我要报修宽带断网 | mock 工单工具 |
| `ticket_create` | 我要创建工单，宽带断网 | mock 业务工具 |
| `ticket_query` | 帮我查工单 TCK-ABC123456 的进度 | mock 业务工具 |
| `human_transfer` | 帮我转人工客服 | 转人工兜底文案 |
| `unknown` | 随便看看这个事情 | 低置信度澄清 |

## 第一阶段已实现内容

第一阶段重点是跑通企业级 Agent 主链路和目录结构，不追求真实 RAG 精度，也不接真实大模型。所有外部系统能力都通过 mock/fallback 保证本地最小版本可启动、可测试、可演示。

## 第二阶段已实现内容

第二阶段把 mock RAG 升级为真实可运行的知识库链路：

1. `data/knowledge/` 文档加载。
2. Markdown/TXT 解析、清洗、中文客服文档分块。
3. Embedding 抽象层和 `MockEmbedding` fallback。
4. 本地 mock vector store，Chroma lazy import，依赖不可用时自动 fallback。
5. MilvusVectorStore placeholder。
6. `/api/chat` 的 FAQ 和故障排查链路返回真实 sources。

## 第三阶段已实现内容

第三阶段把模板式回答升级为可配置的大模型生成链路：

1. 新增 `app/llm/`，支持 `mock`、`dashscope/qwen`、`openai_compatible` 三类 provider。
2. 新增 `app/agents/chains/rag_answer_chain.py`，使用 LCEL 管道表达式组织 RAG Answer Chain。
3. FAQ 和故障排查链路先检索 sources，再生成客服回答。
4. 默认 `temperature=0`，降低回答随机性。
5. 真实 LLM 不可用时 fallback 到 `MockLLM`。
6. sources 为空时不调用 LLM，直接建议转人工客服。
7. `DashScopeEmbedding` 支持 `text-embedding-v4`，真实 embedding 不可用时 fallback 到 `MockEmbedding`。

## 第四阶段已实现内容

第四阶段把单纯规则分类升级为企业级两阶段意图识别和多场景 Router：

1. 新增 `app/agents/intent_schema.py`，统一维护 12 类 intent、slots 约定和结构化结果。
2. 新增 `app/agents/chains/intent_chain.py`，使用 LCEL 组织 LLM 结构化意图识别，并强制解析 JSON。
3. `intent_classifier.py` 支持规则预分类，高置信度直出，低确定性问题交给 LLM；LLM 不可用时 fallback 到规则结果。
4. `router.py` 改为注册式路由表，避免随着 intent 增长堆叠大量 `if/else`。
5. 新增 `package_recommend`、`bill_explain`、`network_repair`、`ticket_query`、`human_transfer`、`unknown` 等细分场景。
6. `confidence < 0.6` 时返回澄清问题，不调用 RAG 或业务工具，降低误路由风险。
7. `MockLLM` 支持 intent JSON 输出，本地没有 API Key 也能演示结构化识别链路。
8. pytest 补充分类器、Router、低置信度兜底测试。

## 第五阶段已实现内容

第五阶段把本地 mock 工具升级为模拟真实业务微服务调用：

1. 新增 `mock_business_service/`，用 FastAPI 模拟 Spring Boot 内部业务服务。
2. 业务服务提供用户、套餐、账单、套餐变更、工单创建和工单查询接口。
3. `app/tools/business_client.py` 新增 `BusinessClient` 抽象、`HttpBusinessClient` 和 `MockBusinessClient` fallback。
4. `PackageTool`、`BillTool`、`TicketTool`、`UserTool` 只通过 `BusinessClient` 访问业务能力。
5. `/api/chat` 业务场景通过 HTTP client 调用业务服务，不直接访问 mock 数据。
6. 工具调用失败时返回友好文案，`tool_calls` 记录 `success=false`、`output`、`latency_ms` 和 `error_message`。
7. `docker-compose.yml` 同时启动 `ai-service` 和 `mock-business-service`，两者通过服务名通信。
8. pytest 补充业务 client、tools HTTP 边界和 chat 业务主链路测试。

## 第六阶段已实现内容

第六阶段把本地会话记忆升级为 Redis 会话记忆与多轮上下文：

1. `app/memory/base.py` 定义异步 `MemoryStore` 接口。
2. `app/memory/memory_store.py` 保留 `InMemoryMemoryStore` fallback。
3. `app/memory/redis_memory.py` 使用 Redis list/string 保存 recent messages、summary 和 key_facts。
4. `app/memory/factory.py` 在 Redis 不可用时自动降级到内存。
5. `ConversationMemoryManager` 负责最近 8 轮、summary buffer 和 key_facts 更新。
6. `QueryRewriter` 实现基础指代消解。
7. RAG 检索使用 `rewritten_query`，响应返回该字段。
8. memory 读写耗时进入 trace 日志。
9. docker compose 新增 Redis 服务。
10. pytest 补充 memory、Redis、query rewrite 和多轮 chat 测试。

## slots 设计

| slot | 含义 |
|---|---|
| `month` | 账单月份，例如 `本月`、`上月`、`2026-06` |
| `target_package` | 用户想办理或咨询的目标套餐 |
| `issue_type` | 问题类型，例如 `network`、`billing`、`package`、`general` |
| `ticket_id` | 售后工单号 |
| `phone_number` | 脱敏手机号 |
| `product_name` | 用户提到的业务产品 |
| `target_user_id` | 客服代查或文本中提到的目标用户 |

后续阶段继续扩展 Redis Cluster、RocketMQ、BGE Embedding、BGE Reranker、Prometheus。
