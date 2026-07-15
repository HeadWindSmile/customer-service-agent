# AI 客服项目 12 讲学习文档设计

## 目标

在 `docs/project_learning_12_lessons.md` 中形成一份可连续学习、可动手验证、可用于面试复习的完整课程。第一讲和第二讲使用当前任务中已经输出的原始文本，不修改标题、措辞、代码示例或面试话术；第三讲至第十二讲基于当前仓库真实实现补齐。

## 读者与使用方式

目标读者是希望通过当前仓库学习 AI Agent 工程实践、并准备 Agent 开发岗位面试的开发者。课程按主请求链路逐层展开，读者可在 PyCharm 中同步打开代码、启动服务并运行示例命令。

## 课程结构

1. 项目整体架构和主链路。
2. `/api/chat` 接口层与数据契约。
3. `CustomerAgent` 主编排。
4. 意图识别与 Router。
5. RAG 检索增强链路。
6. LLM、LCEL 与 Mock fallback。
7. Tools 与业务系统边界。
8. Memory 多轮对话。
9. RBAC 与 Audit。
10. Safety 内容安全。
11. Event、Trace 与 Metrics。
12. Eval、Load Report 与面试讲法。

文档开头增加总目录、学习顺序和能力边界。第一、第二讲保持原文；第三讲至第十二讲统一覆盖简历映射、业务问题、核心文件、调用流程、关键代码、运行验证、生产边界、面试表达和自测题。

## 内容原则

- 所有结论以当前仓库代码和现有设计文档为依据。
- 明确区分当前仓库能力、默认 mock/fallback、placeholder 和生产环境真实接入。
- 不把本地 eval 或 load report 写成生产指标。
- 不声称默认接入真实 Milvus、Redis Cluster、RocketMQ、MySQL、Spring Boot、Prometheus/Grafana 或 OTel Collector。
- 不声称当前 Demo 支持生产级高并发。
- 当前架构描述为“单主 Agent + 多意图子链路”，不夸大为复杂多 Agent 协作。
- 对简历中的生产指标给出合理口径和追问防守方式，不将其归因于当前仓库。

## 链接与命令

第一、第二讲保留原有绝对路径链接。新增课程内容使用仓库相对路径，确保 GitHub 可阅读。Windows 示例优先使用 PowerShell 和 `curl.exe`；通用验证命令使用 `pytest`、`uvicorn`、eval 和 load test 现有入口，不新增脚本或依赖。

## 验收标准

- 单个 Markdown 文件完整包含 12 讲，讲次无缺失和重复。
- 第一、第二讲与当前任务原始输出一致。
- 第三讲至第十二讲均能定位到真实文件和类。
- 示例命令与当前接口、参数和脚本保持一致。
- 文档不存在未解释的生产化承诺或夸大指标。
- 不修改业务代码、配置和已有测试。
