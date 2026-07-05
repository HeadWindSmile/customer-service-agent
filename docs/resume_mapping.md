# 简历成果映射与最终演示口径

## 简历项目概述

本项目对应简历中的企业级 AI 客服问答系统：在原有 Java/Spring Boot 业务系统旁边建设 Python/FastAPI AI 服务层，形成“业务微服务 + AI 服务层（LLM + Agent）”融合架构，面向用户和客服人员提供业务咨询、套餐办理、故障排查、售后服务、Offer 推荐和订单查询等场景能力。

当前仓库是脱敏后的可运行 Demo，重点证明工程结构和主链路：RAG、LCEL、Intent Router、Tools、Memory、RBAC、安全、审计、事件、trace、Prometheus-compatible `/metrics`、eval report 和 load report。默认本地模式使用 mock/fallback，不强制依赖真实外部服务。

## 当前仓库与简历能力总览

| 分类 | 生产项目能力 | 当前仓库能力 | fallback 边界 | 后续真实接入 |
|---|---|---|---|---|
| AI 服务层 | Python/FastAPI 承载 Agent 服务 | `/api/chat`、health、ready、trace、metrics | 本地单进程 Demo | 保持 API 薄封装，接入真实网关和监控 |
| Agent 编排 | LLM + Agent 融合业务系统 | `CustomerAgent` 主编排、Router 注册式分发 | 默认 MockLLM | 配置真实 LLM 后跑评测 |
| RAG | 解析、分块、向量化、召回、Rerank、生成 | 零宽断言分块、MMR、多候选召回、Reranker 抽象、sources、LCEL、TopK eval | 默认 MockEmbedding、MockVectorStore、MockReranker | Milvus、BGE、BGE-Reranker 或企业向量检索服务 |
| 业务融合 | Spring Boot、MySQL、业务 API | `BusinessClient`、HTTP client、mock 业务服务、package/bill/ticket/offer/order | 默认 `MockBusinessClient`，不直连 MySQL | 替换为真实 Spring Boot 内部 API |
| 会话记忆 | Redis Cluster、多实例上下文共享 | memory/Redis 可选、summary、key_facts、query rewrite | Redis 不可用 fallback memory | Redis Cluster、原子会话操作、上下文压缩 |
| 权限安全 | RBAC、审计、内容安全、人工审核 | RBAC、audit、输入/输出/工具参数安全、review queue | 语义检测为 mock | 真实安全审核模型、人工审核后台 |
| 事件机制 | RocketMQ 异步解耦 | EventBus、事件模型、MockEventProducer、RocketMQProducer placeholder | 默认写 `logs/events.jsonl` | 真实 RocketMQ SDK、topic/tag/key、失败隔离 |
| 评测观测 | 准确率、幻觉率、时延、Token 成本、trace | trace、latency breakdown、metrics-lite、`/metrics`、eval、load report | 单进程内存指标，本地小样本评测 | Prometheus/Grafana/OTel、持续评测和人工质检 |

## 技术栈映射表

| 简历技术栈 | 当前仓库证据 | 当前接入状态 | 真实接入计划 |
|---|---|---|---|
| Python | `app/`、`evals/`、`scripts/` | 已实现 | 持续作为 AI 服务主语言 |
| FastAPI | `app/main.py`、`app/api/` | 已实现 | 保持 API 薄封装 |
| LangChain / LCEL | `app/agents/chains/` | 已实现 RAG 和 intent 链路 | 继续用于可评测子链路 |
| qwen-plus / OpenAI-compatible | `DashScopeLLM`、OpenAI-compatible 配置 | 有适配，默认 mock | 配置真实 Key 后跑可选评测 |
| Milvus | `MilvusVectorStore` | 有 lazy 适配，默认 fallback | 配置真实 Milvus 后联调入库、检索和评测 |
| BGE Embedding | `BGEEmbedding` | 有 lazy provider，默认 mock | 安装模型依赖后跑真实 embedding 评测 |
| BGE-Reranker | `BaseReranker`、`BGEReranker`、`MockReranker` | 有抽象和 lazy provider，默认 mock | 安装依赖或接企业 rerank 网关后跑对比评测 |
| Redis Cluster | `RedisMemory`、`FallbackMemoryStore` | Redis 可选，默认 memory | 补 Cluster 配置和原子操作策略 |
| Spring Boot / MySQL | 通过 `mock_business_service` 模拟 HTTP 边界 | 当前不直连真实业务库 | 替换为真实业务服务 |
| RocketMQ | `EventBus`、`RocketMQProducer` placeholder | 有事件模型和占位 producer | 接真实 SDK，失败降级 jsonl |
| Prometheus/Grafana/OTel | `/metrics`、trace 文件 | Prometheus-compatible 文本导出 | 接真实监控平台和告警 |

## 核心职责映射表

| 简历职责 | 当前仓库已完成 | fallback 边界 | 后续真实接入 |
|---|---|---|---|
| Agent 服务与业务微服务融合 | `CustomerAgent`、`BusinessClient`、tools、mock 业务服务 | 本地 mock/fallback 可运行 | 真实 Spring Boot/MySQL 业务服务联调 |
| RAG 知识库链路 | loader、cleaner、splitter、embedding provider、vector store、MMR、reranker、sources、LCEL、TopK eval | 默认 mock 检索组件 | 真实 Milvus/BGE/Reranker 环境和对比报告 |
| 多场景 Router | 15 类 intent、slots、confidence、注册式 Router | 规则 + MockLLM fallback | 增加真实业务域和更细评测集 |
| Java + Python 协同 | HTTP 边界已模拟 | mock 业务服务不是真实 Spring Boot | 保留契约，替换服务端实现 |
| API + MQ 异步解耦 | EventBus、事件模型、mock producer、MQ placeholder | 默认 JSON Lines | 真实 RocketMQ SDK 和失败隔离策略 |
| 评测体系 | TopK、source coverage、tool、安全、疑似幻觉、延迟、估算成本 | 本地小样本，不是生产指标 | 生产评测集、在线反馈和人工质检 |
| 性能与观测 | retry/backoff、circuit breaker、cache、metrics-lite、`/metrics`、load report | 本地小流量，不做容量承诺 | 真实压测环境和监控平台 |

## 成果指标映射表

| 简历成果 | 生产项目指标口径 | 当前仓库可验证内容 | 当前边界 |
|---|---|---|---|
| Top-3 命中率提升 | 生产标注集和真实检索服务统计 | 多候选召回、MMR、Reranker 抽象、Top3 本地评测字段 | 不把生产指标写成本地结果 |
| Top-1 命中率提升 | 生产 Rerank 评测 | Mock/BGE/OpenAI-compatible reranker 接入点、Top1 本地评测字段 | 真实对比需要外部服务和更大评测集 |
| 幻觉率下降 | 生产质检或 LLM-as-judge + 人工抽检 | sources 为空不生成、prompt 约束、简化疑似幻觉检测 | 本地只是规则化疑似检测 |
| 多轮追问准确率 | 生产多轮评测集 | query rewrite、summary、key_facts、Memory 测试 | 仍需更大多轮样本 |
| 意图准确率提升 | 生产意图评测集 | 15 类 intent、分场景 eval | 本地小样本不等同生产评测 |
| 平均延迟优化 | 网关/APM/Prometheus 线上统计 | latency breakdown、`/metrics`、本地 load report | 不宣称本地达到生产容量 |
| 内容安全拦截 | 生产安全样本库指标 | 规则、正则、Mock 语义检测、review queue | 语义检测仍需真实模型或样本库 |
| 定位效率提升 | 生产运维指标 | trace 可回放单次链路 | 本地证明字段和回放能力 |

## 当前已实现能力

1. API 层保持薄封装，`/api/chat` 只接收请求、校验模型并调用 Agent。
2. `CustomerAgent` 负责安全、记忆、改写、意图识别、权限上下文、Router、事件、trace 的主编排。
3. `CustomerRouter` 使用注册式路由表，支持 FAQ、套餐、账单、故障、工单、Offer、Order、转人工和 unknown 等 15 类意图。
4. RAG 层已支持 Markdown/TXT 加载、清洗、零宽断言中文分块、多候选召回、MMR、Reranker 抽象、本地/可选 Milvus 向量库、top_k sources 和 LCEL 生成。
5. LLM 层已支持 MockLLM、DashScope/OpenAI-compatible 适配和失败降级。
6. Tools 层已通过 `BusinessClient` 隔离业务系统，支持套餐、账单、用户、工单、Offer 和 Order 能力。
7. Memory 层已支持 memory/Redis 可选、最近 8 轮、summary、key_facts 和指代消解。
8. Safety 层已覆盖输入、输出和工具参数安全，并把中高风险写入本地 review_queue。
9. Observability 层已支持 trace、span、event、attribute、latency breakdown、metrics-lite、Prometheus-compatible `/metrics`、LLM usage 估算和 trace 回放。
10. Evals 已支持离线数据集、scenario 标签、expected_sources、expected_top_k、expected_rerank、Top1/Top3/TopK、source coverage、intent、工具、安全、简化疑似幻觉、延迟和估算 Token/成本报告。
11. 第 18 阶段已补齐最终演示脚本、最终自检清单、统一演示检查入口和面试讲解口径。

## 当前 mock / fallback / placeholder 能力

| 能力 | 当前形态 | 面试说法 |
|---|---|---|
| LLM | 默认 MockLLM | 保证本地可运行；真实模型通过配置接入 |
| Embedding | 默认 MockEmbedding | BGE/OpenAI-compatible 可选，失败 fallback |
| Vector Store | 默认 MockVectorStore | Milvus 有适配，但默认不要求启动 |
| Reranker | 默认 MockReranker | BGE/HTTP rerank 可选，真实指标需外部环境 |
| Business Service | MockBusinessClient 和 mock_business_service | 证明业务 API 边界，不等于真实 Spring Boot |
| Memory | 默认 memory，Redis 可选 | Redis 不可用不影响本地演示 |
| Event | MockEventProducer，RocketMQProducer 占位 | 当前不连接真实 RocketMQ |
| Safety Semantic | MockSemanticDetector | 后续可接真实安全审核模型 |
| Metrics | metrics-lite、Prometheus-compatible `/metrics` | 当前不是完整监控平台 |

## 需要真实接入的能力清单

1. Milvus：已补连接配置、collection 初始化、向量写入、检索和不可用 fallback；仍需真实环境联调。
2. BGE Embedding：已补 provider 和 fallback；仍需安装模型依赖后跑真实 embedding 评测。
3. BGE-Reranker：已补抽象、trace 字段和 TopK/Rerank 本地评测报告；真实对比仍需外部服务。
4. Redis Cluster：后续补 Cluster URL/节点配置、Lua/事务式会话操作策略和降级说明。
5. RocketMQ：后续补真实 Producer SDK、topic/tag/key、发送失败隔离和本地 jsonl fallback。
6. Spring Boot / MySQL：当前通过业务 API 边界模拟，不让 AI 服务直连业务库；后续替换为真实内部 API。
7. Prometheus/Grafana/OTel：当前 `/metrics` 可被抓取，完整监控平台、告警和长期存储仍是后续接入。

## 当前仓库与真实生产项目差距

当前仓库已经能证明核心工程结构和主链路设计，但还不能证明生产环境容量、真实外部依赖稳定性、真实业务库数据一致性和线上运营指标。面试中应把这些差距讲清楚：生产项目有真实环境与指标，当前仓库是脱敏后可运行版本，适合演示架构边界、测试、评测和本地验证闭环。

## 面试讲解口径

可以这样讲：

> 简历中的生产项目有真实业务系统和基础设施接入。这个仓库是我把生产项目核心架构脱敏后逐步复现的版本，目前已经跑通 AI 服务层、RAG、LCEL、Router、工具调用、RBAC、安全、事件、trace、Prometheus-compatible `/metrics`、eval 和本地性能报告，并已通过 `BusinessClient` 接入 Offer/Order 基础业务域。第 18 阶段已经把 README、演示脚本、评测报告、压测报告和讲解口径整理成最终交付闭环。

当面试官追问指标时，应说明指标来自生产项目或本地评测报告的不同口径。当前仓库能验证的是工程链路、测试用例、本地评测和演示脚本，不把生产指标说成本地 Demo 自动得出的结果。

## 禁止夸大说明

1. 不要说当前仓库默认已经连接真实 Milvus、Redis Cluster、RocketMQ、MySQL 或 Prometheus/Grafana。
2. 不要说本地运行版本已经支持 5 万并发会话或生产级高并发。
3. 不要把生产项目中的 TopK、幻觉率、可用性、满意度等指标写成当前仓库测试结果。
4. 可以说当前仓库已有 BGE-Reranker 接入点和 Mock fallback，但不要说本地默认已经跑过真实 BGE-Reranker 指标。
5. 不要把 `mock_business_service` 描述成真实 Spring Boot 服务，它只是业务边界模拟。
6. 不要把“多 Agent 编排”直接描述成当前已完成能力；当前更准确的说法是“单主 Agent 编排 + 多意图子链路 Router 分发”。

## 第 14-18 阶段真实接入路线图

| 阶段 | 名称 | 状态 | 目标 |
|---|---|---|---|
| 第 14 阶段 | RAG 真实检索增强 | 已完成 | 零宽断言分块、MMR、多候选召回、Reranker 抽象、BGE provider、Milvus 适配和 fallback |
| 第 15 阶段 | AI 评测体系增强 | 已完成 | Top1/Top3/TopK、source coverage、疑似幻觉、意图、工具、安全、延迟、Token 成本报告 |
| 第 16 阶段 | Offer / Order 业务域增强 | 已完成 | 新增 Offer / Order 工具、业务服务契约、RBAC、审计和测试 |
| 第 17 阶段 | 性能与可观测性增强 | 已完成 | Prometheus-compatible `/metrics`、JSON/Markdown 性能报告、trace latency breakdown |
| 第 18 阶段 | 最终面试演示闭环 | 已完成 | 统一 README、简历映射、演示脚本、评测报告、压测报告、验证命令和讲解口径 |

## 第 18 阶段最终交付口径

第 18 阶段不新增大业务功能，不推翻既有架构。验收重点是：

1. README 能让面试官快速理解项目定位、主链路、能力边界和启动验证方式。
2. demo_script 能按顺序覆盖 RAG、Tools、Memory、RBAC、安全、事件、trace、metrics、eval 和 load report。
3. interview_guide 能回答生产项目与当前仓库差异、指标口径、mock/fallback、Prometheus-compatible metrics 和 RocketMQ placeholder。
4. checklist 能作为最终演示前自检表。
5. pytest 能约束文档入口和禁止夸大表述。
