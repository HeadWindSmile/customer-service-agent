# 部署设计说明

## 目标

第 11 阶段已经让项目具备本地部署和面试演示能力。第 12 阶段只整理启动方式，不引入复杂进程管理。

## Docker Compose 部署图

```mermaid
flowchart TB
    Host["本机"] --> AI["ai-service:8000"]
    Host --> Biz["mock-business-service:8010"]
    Host --> Redis["redis:6379"]
    AI --> Biz
    AI --> Redis
    AI --> Logs["app-logs volume"]
    AI --> Vector["vector-store volume"]
    Redis --> RedisData["redis-data volume"]
```

## 本地最小模式

只启动 AI 服务：

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

此时：

1. `LLM_PROVIDER=mock`。
2. `MEMORY_BACKEND=memory`。
3. `EVENT_PRODUCER=mock`。
4. `BUSINESS_SERVICE_BASE_URL` 为空，业务工具走 `MockBusinessClient`。

## 双服务模式

模拟 AI 服务调用原有 Spring Boot 业务系统：

```bash
uvicorn mock_business_service.main:app --host 127.0.0.1 --port 8010
```

另开终端：

```bash
$env:BUSINESS_SERVICE_BASE_URL="http://127.0.0.1:8010"
uvicorn app.main:app --reload
```

## Docker Compose

```bash
docker compose up -d
docker compose ps
docker compose logs ai-service
```

Compose 默认启动：

1. `ai-service`
2. `mock-business-service`
3. `redis`

## 健康检查

| 接口 | 说明 |
|---|---|
| `GET /health` | 应用进程存活 |
| `GET /ready` | 依赖就绪检查 |
| `GET /metrics-lite` | 单进程轻量指标 |

`/ready` 会检查 app、memory backend、business service、vector store、LLM provider、event producer 和 trace storage。Redis、LLM、事件生产者属于可降级依赖；显式配置业务服务后，业务服务不可用会让 readiness 失败。

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/dev_start.sh` | Linux/macOS 本地启动 |
| `scripts/dev_start.ps1` | Windows 本地启动 |
| `scripts/run_tests.sh` | Linux/macOS 运行 pytest |
| `scripts/run_tests.ps1` | Windows 运行 pytest |
| `scripts/run_eval.sh` | Linux/macOS 运行评测 |
| `scripts/demo_check.ps1` | Windows 演示前核心检查 |
| `scripts/smoke_test.py` | 服务启动后的冒烟验证 |
| `scripts/simple_load_test.py` | 本地小规模并发验证 |

这些脚本只做简单命令封装，不引入复杂进程管理。

## 当前边界

1. 不声称支持生产级高并发。
2. 不默认启动 Milvus、Prometheus、Grafana 或 OTel Collector。
3. RocketMQ 当前是 placeholder。
4. `simple_load_test.py` 只用于本地小流量验证。

