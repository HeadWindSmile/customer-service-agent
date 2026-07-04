# 第 12 阶段交付自检清单

## 启动检查

- [ ] `pip install -r requirements.txt` 可安装依赖。
- [ ] `uvicorn app.main:app --reload` 可启动 AI 服务。
- [ ] `docker compose up -d` 可启动 `ai-service`、`mock-business-service`、`redis`。
- [ ] `GET /health` 返回成功。
- [ ] `GET /ready` 返回结构化依赖状态。

## API 检查

- [ ] 套餐规则咨询返回 `faq_query` 和非空 `sources`。
- [ ] 当前套餐查询返回 `package_query` 和 `query_user_package` tool call。
- [ ] 账单查询返回 `bill_query` 和 `query_bill` tool call。
- [ ] 故障排查返回 RAG sources。
- [ ] 工单创建返回 `create_ticket` tool call 和工单号。

## 可观测性检查

- [ ] `/api/chat` 响应包含 `trace_id`。
- [ ] `GET /api/traces/{trace_id}` 可查询 trace。
- [ ] trace 中能看到 intent、sources、tool_calls、safety 和 event publish 摘要。
- [ ] `GET /metrics-lite` 可返回单进程轻量指标。

## 权限、安全、审计检查

- [ ] 普通用户不能查询其他用户。
- [ ] 客服代查必须提供 `target_user_id`。
- [ ] 客服代查账单写入 `logs/audit.log`。
- [ ] 安全高风险输入被拦截。
- [ ] 高风险安全事件进入 `logs/review_queue.jsonl`。

## fallback 检查

- [ ] 未配置真实 LLM 时使用 `MockLLM`。
- [ ] 未配置业务服务地址时使用 `MockBusinessClient`。
- [ ] Redis 不可用时可 fallback 到 memory。
- [ ] `EVENT_PRODUCER=mock` 时事件写入 `logs/events.jsonl`。
- [ ] RocketMQ 当前只作为 placeholder 说明，不作为真实依赖。

## 文档检查

- [ ] README 是项目说明书，不只是启动说明。
- [ ] `docs/interview_guide.md` 包含 30 秒、2 分钟、5 分钟讲解。
- [ ] `docs/demo_script.md` 包含至少 5 个真实业务案例。
- [ ] 架构图使用 Mermaid 或 ASCII，不生成图片。
- [ ] 文档没有把本地 Demo 描述成生产容量、真实 MQ、真实向量库或完整监控平台。

## 简历映射自检

- [ ] `docs/resume_mapping.md` 存在，并包含技术栈、职责、成果指标和第 14-18 阶段路线图。
- [ ] 文档能区分生产项目真实能力、当前仓库已实现能力、mock/fallback/placeholder 边界和后续真实接入计划。
- [ ] README 只提供简历映射入口，不重复堆砌长篇简历内容。
- [ ] interview_guide 能解释生产项目与当前仓库差异。
- [ ] demo_script 能说明哪些能力用于现场演示，哪些能力属于后续真实接入。
- [ ] 没有把生产指标写成当前本地仓库的自动化测试结果。
- [ ] 后续阶段如果真实接入 Milvus、BGE、RocketMQ、Offer/Order 或 `/metrics`，需要同步更新 resume_mapping、README 和面试话术。

## 第 14 阶段 RAG 检索增强自检

- [ ] 中文分块使用句末零宽断言，句号、问号、叹号等标点保留在原句内。
- [ ] chunk 保留 `title`、`section`、`source` 和原始 `metadata`。
- [ ] RAG 检索支持 `RAG_CANDIDATE_COUNT` 多候选召回。
- [ ] MMR 可通过 `RAG_MMR_ENABLED` 和 `RAG_MMR_LAMBDA` 配置。
- [ ] Reranker 通过 `BaseReranker` 抽象接入，默认 `MockReranker` 可运行。
- [ ] BGE Embedding 和 BGE/OpenAI-compatible Reranker 外部依赖不可用时会 fallback。
- [ ] `VECTOR_STORE=milvus` 但未配置或连接失败时会 fallback 到 MockVectorStore。
- [ ] trace 包含 `vector_store_type`、`embedding_provider`、`candidate_count`、`mmr_enabled`、`reranker_used`、`reranker_type`、`final_top_k`。
- [ ] pytest 覆盖 splitter、MMR、reranker、Milvus fallback 和 retriever trace。

## 第 15 阶段 AI 评测体系增强自检

- [ ] `evals/datasets/customer_qa_eval.jsonl` 覆盖 `faq`、`bill_explain`、`fault_diagnosis`、`tool`、`safety` 场景。
- [ ] 数据集支持 `expected_sources`、`expected_top_k`、`expected_rerank` 和 `scenario` 标签。
- [ ] `evals/metrics.py` 输出 Top1、Top3、TopK、source coverage、Rerank 期望、intent、tool、安全、疑似幻觉、延迟和估算 Token/成本。
- [ ] `evals/run_eval.py` 可以复用 `/api/chat` 响应和 `/api/traces/{trace_id}`，trace 不可用时能 fallback。
- [ ] JSON 报告和 Markdown 报告都能生成到 `evals/reports/`。
- [ ] 报告明确区分“本地 Demo 评测结果”和“生产项目指标口径”。
- [ ] pytest 覆盖 metrics、dataset 加载和 report 输出。
- [ ] 文档没有把生产 TopK、幻觉率、延迟或成本指标写成本地 Demo 结果。

## 测试检查

```bash
pytest
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
python evals/run_eval.py --base-url http://127.0.0.1:8000
```
