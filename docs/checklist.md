# 第 18 阶段最终面试交付自检清单

本清单用于最终面试前自检。目标是证明当前仓库可以被快速理解、启动、验证和追问，同时明确 mock/fallback/placeholder 边界，不把本地 Demo 说成生产系统。

## 启动检查

- [ ] `pip install -r requirements.txt` 可安装依赖。
- [ ] `uvicorn app.main:app --reload` 可启动 AI 服务。
- [ ] `GET /health` 返回成功。
- [ ] `GET /ready` 返回结构化依赖状态。
- [ ] 可选：`docker compose up -d` 可启动 `ai-service`、`mock-business-service`、`redis`。

## API 主链路检查

- [ ] `/api/chat` 响应包含 `answer`、`intent`、`confidence`、`trace_id`、`latency_ms`。
- [ ] 套餐规则咨询返回 `faq_query` 和非空 `sources`。
- [ ] 当前套餐查询返回 `package_query` 和 `query_user_package` tool call。
- [ ] 账单查询返回 `bill_query` 和 `query_bill` tool call。
- [ ] 故障排查返回 RAG sources。
- [ ] 工单创建返回 `create_ticket` tool call 和工单号。
- [ ] Offer 查询或推荐返回 `offer_query` / `offer_recommend` 和对应 tool call。
- [ ] 订单查询返回 `order_query`，客服代查时写入审计。

## RAG Sources 检查

- [ ] RAG 响应的 `sources` 包含 `doc_id`、`title`、`content`、`score`、`metadata`。
- [ ] trace 中能看到 `rag.retrieve`、`rag.answer`、`rag_retrieval.source_count`。
- [ ] trace 中能看到 `vector_store_type`、`embedding_provider`、`candidate_count`、`mmr_enabled`、`reranker_used`、`final_top_k` 等检索配置。
- [ ] sources 为空时系统兜底转人工，不编造套餐、费用或赔偿承诺。

## Tools 检查

- [ ] `tool_calls` 包含 `tool_name`、`input`、`output`、`success`、`latency_ms`。
- [ ] `permission_checked=true` 能证明工具调用前做过权限校验。
- [ ] `audit_logged=true` 能证明敏感操作写入审计。
- [ ] `PackageTool`、`BillTool`、`TicketTool`、`OfferTool`、`OrderTool` 均只通过 `BusinessClient` 访问业务能力。

## Memory 检查

- [ ] 同一 `user_id + session_id` 下，先查套餐再追问“这个套餐什么时候生效”可触发上下文改写。
- [ ] 响应或 trace 中能看到 `rewritten_query`。
- [ ] trace 中能看到 `memory_backend`、`memory_turn_count`、`memory_key_fact_keys`。
- [ ] Redis 不可用时可 fallback 到 memory。

## RBAC / Audit 检查

- [ ] 普通用户不能查询其他用户的账单、套餐、工单或订单。
- [ ] 客服代查必须提供 `target_user_id`。
- [ ] 客服代查账单或订单写入 `logs/audit.log`。
- [ ] 审计日志中的 actor、target、手机号、身份证、银行卡、邮箱等敏感字段已脱敏。

## Safety 检查

- [ ] prompt injection 高风险输入返回 `SAFETY_INPUT_BLOCKED`。
- [ ] 高风险输入不进入 LLM、RAG 或业务工具。
- [ ] `safety_result.input_safety` 包含 `risk_level`、`action`、`findings`。
- [ ] 中高风险事件进入 `logs/review_queue.jsonl`。
- [ ] 安全事件发布 `SAFETY_REVIEW_REQUIRED`。

## Event 检查

- [ ] `EVENT_PRODUCER=mock` 时事件写入 `logs/events.jsonl`。
- [ ] 创建工单后出现 `TICKET_CREATED`。
- [ ] 敏感审计后出现 `AUDIT_LOG_CREATED`。
- [ ] 每次问答结束出现 `AI_QA_FINISHED`。
- [ ] RocketMQ 当前只作为 placeholder 说明，不作为真实依赖。

## Trace / Metrics 检查

- [ ] `/api/chat` 响应包含 `trace_id`。
- [ ] `GET /api/traces/{trace_id}` 可查询 trace。
- [ ] trace 中能看到 intent、sources、tool_calls、safety、event publish 摘要。
- [ ] trace 中能看到 `attributes.latency_breakdown`，包含 safety、memory、intent、router、RAG、tool、event 等阶段耗时。
- [ ] `GET /metrics-lite` 可返回单进程轻量 JSON 指标。
- [ ] `GET /metrics` 可返回 Prometheus-compatible 文本指标。
- [ ] metrics 标签不包含 trace_id、user_id、session_id、订单号、原始问题或错误堆栈。

## Eval Report 检查

- [ ] `python evals/run_eval.py --base-url http://127.0.0.1:8000` 可生成 JSON 和 Markdown 报告。
- [ ] `evals/reports/latest_report.md` 包含 intent、TopK、source coverage、tool、安全、疑似幻觉、延迟和估算 Token/成本。
- [ ] 报告明确说明本地 Demo 评测结果不代表生产项目历史指标。

## Load Report 检查

- [ ] `python scripts/simple_load_test.py --base-url http://127.0.0.1:8000 --scenario mixed --concurrency 5 --total-requests 20 --report reports/phase18_load_test.json --markdown-report reports/phase18_load_test.md` 可生成报告。
- [ ] 报告包含 avg、p50、p95、max、success_rate、error_rate、intent 分布和 status_code 分布。
- [ ] 报告明确说明本地小流量验证不代表生产容量承诺或线上 SLA。

## 文档一致性检查

- [ ] README 当前阶段为第 18 阶段最终面试演示闭环。
- [ ] `docs/resume_mapping.md` 区分生产项目能力、当前仓库能力、fallback 边界和后续真实接入。
- [ ] `docs/demo_script.md` 覆盖 RAG、Tools、Memory、RBAC、安全、事件、trace、metrics、eval、load report。
- [ ] `docs/interview_guide.md` 包含 30 秒、2 分钟、5 分钟讲解和常见追问回答。
- [ ] 文档没有把 Milvus、Redis Cluster、RocketMQ、Prometheus/Grafana/OTel、MySQL 或真实 Spring Boot 描述成本地默认依赖。
- [ ] 文档没有把本地 Demo 描述成可承诺线上容量或高并发 SLA。

## 最终验收命令

```bash
pytest
uvicorn app.main:app --reload
python scripts/final_demo_check.py --base-url http://127.0.0.1:8000
python evals/run_eval.py --base-url http://127.0.0.1:8000
python scripts/simple_load_test.py --base-url http://127.0.0.1:8000 --scenario mixed --concurrency 5 --total-requests 20 --report reports/phase18_load_test.json --markdown-report reports/phase18_load_test.md
```
