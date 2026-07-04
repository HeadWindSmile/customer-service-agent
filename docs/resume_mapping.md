# 简历成果映射与真实接入路线图

## 简历项目概述

本项目对应简历中的企业级 AI 客服问答系统：在原有 Java/Spring Boot 业务系统旁边建设 Python/FastAPI AI 服务层，形成“业务微服务 + AI 服务层（LLM + Agent）”融合架构，面向用户和客服人员提供业务咨询、套餐办理、故障排查、售后服务等场景能力。

第 13 阶段的目标不是新增业务功能，而是把简历中的生产项目能力、当前仓库已落地能力、仍处于 mock/fallback/placeholder 的能力、以及第 14-18 阶段真实接入路线统一整理出来。后续阶段的方向是“真实接入优先，fallback 保底”：外部系统可用时走真实链路，本地最小模式仍可降级运行。

## 当前仓库与简历能力总览

| 分类 | 简历生产项目能力 | 当前仓库状态 | 后续动作 |
|---|---|---|---|
| AI 服务层 | Python/FastAPI 承载 Agent 服务 | 已实现 `/api/chat`、health、trace API | 保持薄 API，不把业务逻辑写入 API 层 |
| Agent 编排 | LLM + Agent 服务融合业务系统 | 已实现 `CustomerAgent` 主编排和 Router 分发 | 后续增强多子链路和业务域，不推翻主编排 |
| RAG | 解析、分块、向量化、召回、Rerank、生成 | 已有解析、清洗、分块、MockEmbedding、向量库抽象、sources、LCEL 生成 | 第 14 阶段补真实 Milvus、BGE、MMR、Reranker 抽象 |
| LLM | qwen-plus、LCEL | 已有 LCEL、DashScope/OpenAI-compatible 适配、MockLLM fallback | 后续用真实 qwen-plus 配置跑评测，不影响本地 fallback |
| 会话记忆 | Redis Cluster、分布式会话隔离 | 已有 RedisMemory 可选、memory fallback、summary、key_facts | 后续增强 Redis Cluster 配置说明和原子会话操作 |
| 业务融合 | Spring Boot、MySQL 8.0、业务 API、RocketMQ | 已有 BusinessClient、HTTP client、mock_business_service、EventBus | 第 16-17 阶段补 offer/order、真实业务服务和 MQ 接入路径 |
| 权限安全 | RBAC、审计、内容安全、人工审核 | 已有 RBAC、audit、输入/输出/工具参数安全、review_queue | 后续补真实语义安全模型或样本库接入点 |
| 评测观测 | 准确率、幻觉率、时延、Token 成本、trace | 已有 trace、metrics-lite、evals、估算 token/cost | 第 15 和 17 阶段补更完整指标与 Prometheus-compatible `/metrics` |

## 技术栈映射表

| 简历技术栈 | 当前仓库证据 | 当前接入状态 | 真实接入计划 |
|---|---|---|---|
| Python | `app/`、`evals/`、`scripts/` | 已实现 | 持续作为 AI 服务主语言 |
| FastAPI | `app/main.py`、`app/api/` | 已实现 | 保持 API 薄封装 |
| LangChain | `app/agents/chains/` | 已实现 LCEL 链路 | 继续用于 RAG、intent、summary 等链路 |
| LCEL | `RagAnswerChain`、`IntentChain` | 已实现 | 后续补更多子链路评测 |
| 通义千问 qwen-plus | `DashScopeLLM`、OpenAI-compatible 配置 | 有适配，默认 mock | 后续用真实 Key 跑可选评测 |
| Milvus | `MilvusVectorStore` placeholder | 尚未真实连接 | 第 14 阶段补真实适配和 fallback |
| BGE-large-zh-v1.5 | `BaseEmbedding` 抽象 | 尚未实现专用 provider | 第 14 阶段补 BGE provider 配置 |
| BGE-Reranker | 文档中作为扩展方向 | 尚未实现 | 第 14 阶段补 Reranker 抽象与可选实现 |
| Redis Cluster | `RedisMemory`、`FallbackMemoryStore` | 有 Redis 单点接口和 fallback | 后续补 Cluster 配置与 Lua/原子操作路线 |
| MySQL 8.0 | 当前通过 mock 业务服务模拟业务数据 | 尚未真实接入 | 第 16 阶段通过业务服务边界补 order/offer，不让 AI 直连业务库 |
| Spring Boot | `mock_business_service` 模拟内部 API | 当前为 FastAPI mock 服务 | 后续保留 HTTP 契约，替换为真实业务服务 |
| RocketMQ | `EventBus`、`RocketMQProducer` placeholder | 有事件模型和占位 producer | 后续补真实 SDK，失败降级 jsonl |
| Prometheus/Grafana/OTel | `metrics-lite`、trace 文件 | 当前为轻量本地观测 | 第 17 阶段补 Prometheus-compatible `/metrics`，不默认依赖外部平台 |

## 核心职责映射表

| 简历职责 | 当前仓库已完成 | 需要补齐 |
|---|---|---|
| Agent 服务与业务微服务融合 | `CustomerAgent`、`BusinessClient`、tools、mock 业务服务 | 真实 Spring Boot/MySQL 业务服务联调 |
| RAG 知识库链路 | loader、cleaner、splitter、embedding、vector store、retriever、sources、LCEL | BGE、Milvus、MMR、Reranker |
| 多场景 Agent、Router、记忆策略 | 12 类 intent、slots、confidence、Router、summary、key_facts | 更细业务域和多子链路演示 |
| Java + Python 跨语言协同 | HTTP 边界已模拟 | 真实 Java 服务、接口契约和错误码对齐 |
| API + RocketMQ 异步解耦 | EventBus、事件模型、mock producer、MQ placeholder | 真实 RocketMQ SDK 和失败降级策略 |
| Prompt、召回、TopK、Rerank 优化 | prompt 强约束、top_k、sources 兜底、缓存 | TopK 评测、MMR、Reranker 对比报告 |
| AI 评测体系 | intent、关键词、sources、tool、安全、幻觉标记、延迟 | Top1/Top3、Token 成本、分场景报告 |
| RBAC 与基础业务模块 | user/package/bill/ticket、RBAC、audit | offer/order 业务域 |
| 性能调优和稳定性 | HTTP 连接复用、retry/backoff、circuit breaker、cache、metrics-lite | 性能报告、Prometheus-compatible metrics、真实压测口径 |

## 成果指标映射表

| 简历成果 | 生产项目指标口径 | 当前仓库可验证内容 | 第 13 阶段表述边界 |
|---|---|---|---|
| Top-3 命中率 55% -> 82% | 生产评测集指标 | 当前仅有 sources 召回和简化评测 | 不把该指标写成本地结果，第 15 阶段补评测口径 |
| Top-1 命中率 45% -> 78% | 生产 Rerank 评测 | 当前无 Reranker | 第 14-15 阶段补 MMR/Reranker 与报告 |
| 幻觉率 30% -> 5% 以下 | 生产问答质检指标 | 当前有 sources 为空不生成、prompt 约束、简化幻觉率 | 本地只说明策略，不冒充生产指标 |
| 多轮追问准确率 92% | 生产多轮评测 | 当前有 query rewrite、summary、key_facts 测试 | 后续补多轮评测集 |
| 意图准确率 72% -> 95% | 生产意图评测 | 当前有 12 类 intent 和基础 eval | 第 15 阶段补更完整意图数据集 |
| 平均延迟 4.8s -> 2.7s | 生产 Prometheus 统计 | 当前有 latency、metrics-lite、本地压测脚本 | 不宣称本地达到生产容量 |
| 内容安全拦截率 100% | 生产安全样本库指标 | 当前有规则、正则、Mock 语义检测和 review_queue | 后续补真实语义检测或样本评测 |
| 问题定位效率提升 83% | 生产运维指标 | 当前 trace 可回放单次链路 | 本地证明可观测字段和回放能力 |
| 业务价值提升 | 生产运营指标 | 当前不能由仓库直接证明 | 面试中作为生产项目结果，不作为本地验收结论 |

## 当前已实现能力

1. API 层保持薄封装，`/api/chat` 只接收请求、校验模型并调用 Agent。
2. `CustomerAgent` 负责安全、记忆、改写、意图识别、权限上下文、Router、事件、trace 的主编排。
3. `CustomerRouter` 使用注册式路由表，支持 FAQ、套餐、账单、故障、工单、转人工和 unknown 等 12 类意图。
4. RAG 层已支持 Markdown/TXT 加载、清洗、中文客服文档分块、本地向量库、top_k sources 和 LCEL 生成。
5. LLM 层已支持 MockLLM、DashScope/OpenAI-compatible 适配和失败降级。
6. Tools 层已通过 `BusinessClient` 隔离业务系统，支持套餐、账单、用户和工单能力。
7. Memory 层已支持 memory/Redis 可选、最近 8 轮、summary、key_facts 和指代消解。
8. Safety 层已覆盖输入、输出和工具参数安全，并把中高风险写入本地 review_queue。
9. Observability 层已支持 trace、span、event、attribute、metrics-lite、LLM usage 估算和 trace 回放。
10. Evals 已支持离线数据集、intent、关键词、sources、工具、安全、简化幻觉率和平均延迟。

## 当前 mock / fallback / placeholder 能力

这些能力不是最终目标，而是为了保证本地最小模式可启动。后续真实接入时仍保留 fallback，避免外部依赖不可用时主链路整体不可用。

| 能力 | 当前形态 | 后续方向 |
|---|---|---|
| LLM | 默认 MockLLM | 配置 qwen-plus 后走真实模型 |
| Embedding | 默认 MockEmbedding | 增加 BGE 或兼容 embedding provider |
| Vector Store | MockVectorStore，Chroma lazy import，Milvus placeholder | 接入真实 Milvus，失败 fallback |
| Business Service | MockBusinessClient 和 mock_business_service | 替换为真实 Spring Boot 内部 API |
| Memory | 默认 memory，Redis 可选 | 接入 Redis Cluster 配置与原子操作策略 |
| Event | MockEventProducer，RocketMQProducer 占位 | 接入真实 RocketMQ SDK |
| Safety Semantic | MockSemanticDetector | 接入真实安全审核模型或样本库评测 |
| Metrics | metrics-lite | 增加 Prometheus-compatible `/metrics` |

## 需要真实接入的能力清单

1. Milvus：补连接配置、collection 初始化、向量写入、检索和不可用 fallback。
2. BGE Embedding：补本地或服务化 embedding provider，明确 batch、timeout 和 fallback。
3. MMR + BGE-Reranker：先召回候选，再重排输出 TopK，并写入 trace 和评测报告。
4. Redis Cluster：补 Cluster URL/节点配置、Lua/事务式会话操作策略和降级说明。
5. RocketMQ：补真实 Producer SDK、topic/tag/key、发送失败隔离和本地 jsonl fallback。
6. Offer / Order：新增业务域，但 AI 服务仍通过业务 API 调用，不直接操作 MySQL。
7. Prometheus-compatible metrics：补 `/metrics` 文本格式，后续可被 Prometheus 抓取。
8. 评测报告：补 Top1/Top3、召回覆盖、Rerank 对比、幻觉、安全、工具、延迟、Token 成本。

## 当前仓库与真实生产项目差距

当前仓库已经能证明核心工程结构和主链路设计，但还不能证明生产环境容量、真实外部依赖稳定性、真实业务库数据一致性和线上运营指标。面试中应把这些差距讲清楚：生产项目有真实环境与指标，当前仓库是脱敏后可运行版本，后续阶段会按真实接入路线逐步补齐。

## 面试讲解口径

可以这样讲：

> 简历中的生产项目是真实接入 Milvus、Redis Cluster、RocketMQ、Spring Boot 和业务库的 AI 客服系统。这个仓库是我把生产项目核心架构脱敏后逐步复现的版本，目前已经跑通 AI 服务层、RAG、LCEL、Router、工具调用、RBAC、安全、事件和 trace。后续阶段会按真实接入优先、fallback 保底的原则，把 Milvus、BGE、Reranker、RocketMQ、Offer/Order 和 Prometheus-compatible metrics 逐步接进来。

当面试官追问指标时，应说明指标来自生产项目或评测报告，当前仓库能验证的是工程链路、测试用例、本地评测和演示脚本。不要把生产指标说成本地 Demo 自动得出的结果。

## 禁止夸大说明

1. 不要说当前仓库已经连接真实 Milvus、Redis Cluster、RocketMQ、MySQL 或 Prometheus/Grafana。
2. 不要说本地运行版本已经支持 5 万并发会话或生产级高并发。
3. 不要把生产项目中的 TopK、幻觉率、可用性、满意度等指标写成当前仓库测试结果。
4. 不要说当前仓库已经完成真实 BGE-Reranker，除非第 14 阶段代码和测试已经落地。
5. 不要把 `mock_business_service` 描述成真实 Spring Boot 服务，它只是业务边界模拟。
6. 不要把“多 Agent 编排”直接描述成当前已完成能力；当前更准确的说法是“单主 Agent 编排 + 多意图子链路 Router 分发”。

## 第 14-18 阶段真实接入路线图

| 阶段 | 名称 | 目标 |
|---|---|---|
| 第 14 阶段 | RAG 真实检索增强 | 增加零宽断言句末分块、MMR、多候选召回、Reranker 抽象、BGE provider、Milvus 真实适配，并保留 mock fallback |
| 第 15 阶段 | AI 评测体系增强 | 增加 Top1/Top3/TopK 命中率、召回覆盖率、幻觉率、意图准确率、工具准确率、安全拦截率、延迟和 Token 成本报告 |
| 第 16 阶段 | Offer / Order 业务域增强 | 新增商品 offer、订单 order 的业务工具、业务服务契约和测试，保持 AI 服务不直连业务库 |
| 第 17 阶段 | 性能与可观测性增强 | 增加 Prometheus-compatible `/metrics`、性能报告、trace latency 字段和压测报告模板，为真实监控平台接入做准备 |
| 第 18 阶段 | 最终面试演示闭环 | 统一 README、简历映射、演示脚本、评测报告、压测报告和面试讲解口径，形成完整交付包 |

## 第 13 阶段验收口径

第 13 阶段完成后，不要求新增环境变量，不新增前端页面，不修改业务主链路。验收重点是文档是否把“当前已实现、当前降级边界、真实接入路线、生产项目指标口径”讲清楚，并通过 pytest 保证文档入口和禁止夸大规则稳定存在。
