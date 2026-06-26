# 企业级 AI 客服问答系统 Demo

## 项目定位

本项目用于 Agent 开发岗位面试展示。它不是普通 ChatBot，而是在原有 Java/Spring Boot 主业务系统旁边新增一层 Python/FastAPI AI 服务，模拟“业务微服务 + AI 服务层（LLM + Agent）”融合架构。

## 当前阶段能力

当前处于第 1 阶段：最小可运行企业骨架。

已实现：

1. `POST /api/chat` 接口。
2. 规则版意图识别，支持 6 类意图：`faq_query`、`package_query`、`package_change`、`bill_query`、`fault_diagnosis`、`ticket_create`。
3. Router 分发机制：FAQ 和故障排查走 mock RAG，套餐、账单、工单走 mock 业务工具。
4. mock Spring Boot 业务客户端边界，AI 服务不直接操作业务数据库。
5. 内存版会话记忆，保留最近 8 轮。
6. 最小 RBAC：普通用户只能查自己，客服可代查并输出审计日志。
7. 最小内容安全：输入敏感词检查、输出高危承诺检查。
8. 结构化响应：`answer`、`intent`、`slots`、`sources`、`tool_calls`、`trace_id`、`latency_ms`。
9. 结构化 JSON 日志和轻量 trace。

## 架构说明

```text
POST /api/chat
  -> api/chat.py 参数校验
  -> customer_agent.py 主编排
  -> permission.py 权限校验
  -> guard.py 输入安全检查
  -> intent_classifier.py 意图识别
  -> router.py 路由分发
  -> rag mock / tools mock
  -> guard.py 输出安全检查
  -> tracing.py + logger.py 记录 trace
  -> 返回结构化结果
```

## 启动方式

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 测试方式

```bash
pytest
```

## curl 示例

FAQ 查询：

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"u1001\",\"session_id\":\"s1\",\"role\":\"user\",\"message\":\"套餐变更什么时候生效？\"}"
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

## 6 类意图示例

| 意图 | 示例问题 | 当前链路 |
|---|---|---|
| `faq_query` | 套餐变更什么时候生效？ | mock RAG |
| `package_query` | 查询我的当前套餐 | mock 业务工具 |
| `package_change` | 我要办理5G畅享套餐 | mock 业务工具 |
| `bill_query` | 帮我查本月账单 | mock 业务工具 |
| `fault_diagnosis` | 宽带不能上网怎么办？ | mock RAG + 工单建议 |
| `ticket_create` | 我要创建工单，宽带断网 | mock 业务工具 |

## 第一阶段已实现内容

第一阶段重点是跑通企业级 Agent 主链路和目录结构，不追求真实 RAG 精度，也不接真实大模型。所有外部系统能力都通过 mock/fallback 保证本地最小版本可启动、可测试、可演示。

## 第二阶段扩展计划

第二阶段会把当前 mock RAG 升级为真实知识库链路，计划补充：

1. `data/knowledge/` 文档加载。
2. Markdown/TXT 解析、清洗、中文客服文档分块。
3. Embedding 抽象层和 mock embedding fallback。
4. Chroma 本地向量库 fallback。
5. MilvusVectorStore 真实适配预留。
6. 后续继续扩展 Redis Cluster、qwen-plus、RocketMQ、BGE Embedding、BGE Reranker、Prometheus。

