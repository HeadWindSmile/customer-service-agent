# 面试讲解稿

## 30 秒项目介绍

这个项目是一个企业级 AI 客服问答系统 Demo，不是普通 ChatBot。它模拟在原有 Spring Boot 主业务系统旁边新增 Python/FastAPI AI 服务层，让用户问题经过安全、记忆、意图识别、Router 分发后，知识类问题走 RAG，套餐、账单、工单等业务问题走工具调用。同时系统有 RBAC、审计、事件、trace 和评测，重点展示 Agent 工程化能力。

## 2 分钟项目介绍

项目背景是企业已有业务系统，AI 服务不能直接查业务库，也不能让大模型随意决定业务动作。所以我把系统拆成几个边界：API 层只接收请求；`CustomerAgent` 做主编排；`IntentClassifier` 负责规则 + LLM 结构化意图识别；`CustomerRouter` 根据 intent 分发；RAG 层负责知识库检索和 sources；Tools 层通过 `BusinessClient` 调用模拟 Spring Boot 的内部 API。

为了让它更像企业项目，我还加了多轮 memory、RBAC、audit、安全检测、事件和 trace。比如客服代用户查账单必须带 `target_user_id`，工具调用前会检查权限，敏感操作会写审计日志。每次请求会生成 `trace_id`，可以回放 RAG、LLM、工具、安全和事件投递过程。

当前 Demo 默认用 mock/fallback，保证本地没有真实 LLM、Milvus、BGE、Reranker、Redis、RocketMQ、数据库或外部监控平台也能启动。生产环境可以把这些边界替换为 Redis Cluster、Milvus、真实 RocketMQ 和 Prometheus/Grafana，但当前 Demo 不夸大这些能力。

## 如何解释生产项目与当前仓库差异

推荐口径：

> 简历里的项目是生产项目，真实接入了业务系统和外部基础设施；当前仓库是脱敏后按阶段复现的版本，已经实现了 AI 服务层、RAG、LCEL、Router、工具调用、RBAC、安全、事件、trace、Prometheus-compatible `/metrics` 和本地性能报告等核心架构。第 14 阶段已经补齐 MMR、Reranker 抽象、BGE provider 和 Milvus 可配置适配，第 16 阶段已补齐 Offer/Order 基础业务域，第 17 阶段已补齐本地性能与可观测性增强；后续继续按“真实接入优先，fallback 保底”的方式接入 RocketMQ 真实 SDK 和完整监控平台。

回答时要把三类内容分开：

1. 生产项目真实能力：可以讲真实线上架构、效果指标和业务价值。
2. 当前仓库已实现能力：可以现场运行、用 curl、trace、eval 和 pytest 证明。
3. 后续真实接入路线：说明当前仍是 mock/fallback/placeholder 的地方，以及哪一阶段补齐。

不要把生产指标说成本地仓库自动跑出的结果，也不要把当前 `mock_business_service` 说成真实 Spring Boot 服务。更准确的讲法是：当前仓库已经复现了架构边界，后续阶段会逐步替换为真实外部系统，同时保留本地 fallback。

## 5 分钟详细讲解

可以按这条主线讲：

1. 业务背景：不是做聊天机器人，而是把 AI 服务层接入原有业务系统。
2. 主链路：`/api/chat` 进入后，先做安全，再加载 memory，做 query rewrite 和意图识别。
3. 分发：FAQ、账单解释、故障排查走 RAG；套餐、账单、工单走工具。
4. 工具边界：工具通过 `BusinessClient` 调用业务服务，不直接访问业务数据。
5. 权限和审计：普通用户只能查自己，客服代查需要 `target_user_id`，敏感操作写 audit。
6. 安全：输入、工具参数、输出都检测，高风险不进入 LLM 或工具。
7. 可观测性：每轮都有 trace、span、latency breakdown、event、tool_calls、sources、safety_result 和 metrics。
8. 部署与兜底：Docker Compose 可启动 AI 服务、mock 业务服务和 Redis；本地默认 mock/fallback。

## 项目架构怎么讲

重点强调三个边界：

1. API 层很薄，不写业务逻辑。
2. Agent 层负责编排，不直接持有业务数据。
3. 业务数据只通过工具层和 BusinessClient 访问。

这样可以回答“为什么不是把所有逻辑写在一个接口里”：因为企业项目需要权限、安全、审计、观测和可替换的外部系统边界。

## RAG 怎么讲

RAG 不是简单读取文本，而是一条可追溯链路：

```text
knowledge docs -> loader -> cleaner -> splitter -> embedding -> vector store -> retriever -> sources -> LCEL answer
```

回答时强调：

1. sources 为空不调用 LLM，避免编造。
2. Prompt 约束模型不能承诺资费、赔偿或办理结果。
3. 当前默认是 mock vector store，已提供 Milvus 可配置适配；未配置或连接失败会 fallback。
4. trace 会记录 source_count、doc_ids、scores 和 cache_hit。

## 意图识别与 Router 怎么讲

当前是两阶段意图识别：

1. 高置信规则直接识别，保证核心客服场景稳定。
2. 低确定性问题交给 LLM 输出 JSON。
3. JSON 结果经过 intent 白名单和 Pydantic 校验。
4. 低置信度时直接澄清，不调用工具。

Router 是注册式路由表，新增 intent 不需要改一大段 `if/else`。

## 工具调用怎么讲

工具调用展示的是 Agent 接入业务系统的能力，不是简单 mock 函数。AI 服务通过 `BusinessClient` 调用业务系统，工具调用结果进入 `tool_calls`，包括参数、输出、成功状态、耗时、权限和审计状态。

生产环境只需要把 mock 业务服务替换成真实 Spring Boot 内部 API，AI 服务层的 Router 和 Tools 边界可以保留。

第 16 阶段新增了 Offer / Order 业务域：Offer 查询和推荐展示业务推荐边界，Order 查询展示敏感订单数据的 RBAC 与审计边界。需要强调当前只做基础查询和推荐，不把 Demo 描述成完整订单交易系统。

## 多轮记忆怎么讲

Memory 按 `user_id + session_id` 隔离，避免串话。最近 8 轮保留原文，更早历史进入 summary，关键业务事实进入 `key_facts`。比如先查当前套餐，再问“这个套餐什么时候生效”，系统可以用 key_facts 做指代消解。

当前 Redis 是可选的，Redis 不可用会 fallback 到内存。生产环境可以换 Redis Cluster。

## 权限、安全、审计怎么讲

回答要点：

1. RBAC 在工具调用前检查，不只是在 API 层判断。
2. 普通用户只能查自己，客服代查必须传 `target_user_id`。
3. 敏感业务操作写 `logs/audit.log`，并脱敏。
4. 安全检查覆盖输入、输出和工具参数。
5. 高风险内容不进入 LLM 和工具。

## RocketMQ placeholder 怎么讲

不要说已经完成真实 MQ 接入。应该说：

> 当前实现了事件模型、Producer 抽象、MockEventProducer 和 RocketMQProducer placeholder。本地默认把事件写入 JSON Lines，目的是演示事件解耦边界。生产环境可以把 Producer 替换为真实 RocketMQ SDK。

## trace/eval 怎么讲

trace 用于单次请求复盘，eval 用于批量质量评估。

trace 里能看到：intent、slots、RAG sources、LLM usage、tool_calls、安全结果、事件投递结果和 latency breakdown。eval 数据集会检查 intent、关键词、sources、tool 和 safety 结果。

## 性能优化与部署怎么讲

当前做了轻量优化：

1. HTTP client 连接复用、retry/backoff、简化 circuit breaker。
2. RAG sources TTL 缓存。
3. `/health`、`/ready`、`metrics-lite` 和 Prometheus-compatible `/metrics`。
4. `simple_load_test.py` 可以生成 JSON/Markdown 本地性能报告。
5. Docker Compose 启动 AI 服务、mock 业务服务和 Redis。

需要明确：当前只是本地部署演示和小规模验证，不声称生产级高并发。

## 项目难点怎么讲

可以讲三个难点：

1. 如何让 LLM 可控：意图白名单、低置信度兜底、sources 为空不生成、工具前权限检查。
2. 如何接业务系统：AI 服务不直接操作数据库，通过 BusinessClient 保持边界。
3. 如何可排查：所有关键步骤进入 trace，工具调用和审计可验证。

## 面试官追问与参考回答

### 为什么不直接让大模型决定调用哪个接口？

因为业务动作有权限、审计和事务边界。模型可以辅助理解意图，但最终只能输出结构化 intent/slots，实际分发由 Router 和权限系统控制。

### 如果 RAG 检索不到资料怎么办？

当前直接返回兜底转人工，不调用 LLM 编造答案。生产可以增加多路召回、reranker 和人工知识补录流程。

### Redis 挂了怎么办？

当前 `FallbackMemoryStore` 会切到内存版，保证本地演示和主链路可用。生产环境需要 Redis Cluster、多副本和监控告警。

### RocketMQ 现在真的发送消息了吗？

没有。当前默认写 `logs/events.jsonl`，RocketMQProducer 是 placeholder。这样做是为了先稳定事件契约和业务边界，避免 Demo 依赖复杂外部系统。

### 为什么要有 audit 和 trace 两套日志？

audit 面向合规和敏感操作留痕，trace 面向单次 Agent 链路排查。两者目的不同，不能互相替代。

### 这个项目和普通后端项目有什么区别？

普通后端项目主要是 CRUD 和接口编排。这个项目重点是 AI Agent 工程化：LLM、RAG、工具调用、记忆、权限、安全、事件和可观测性如何在一条业务链路里协作。
