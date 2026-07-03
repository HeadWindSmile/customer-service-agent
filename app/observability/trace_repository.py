import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.observability.logger import log_event
from app.observability.tracing import TraceContext


class TraceRepository:
    """本地 trace 仓储。

    第十阶段需要支持按 trace_id 回放，但仍不提前引入数据库或 APM 平台。
    因此第一版使用一个 trace 一个 JSON 文件，便于本地演示和 pytest 断言。
    """

    def __init__(self, storage_dir: str | None = None, enabled: bool | None = None) -> None:
        self.storage_dir = Path(storage_dir or settings.trace_storage_dir)
        self.enabled = settings.trace_enabled if enabled is None else enabled

    def save(self, trace: TraceContext) -> bool:
        if not self.enabled:
            return False
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            path = self._path_for(trace.trace_id)
            path.write_text(
                json.dumps(trace.to_dict(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            return True
        except Exception as exc:
            # trace 写入失败不能影响 /api/chat 主链路，真实生产可接备用日志或队列。
            log_event("trace.write_failed", {"trace_id": trace.trace_id, "error": str(exc)}, level="error")
            return False

    def get(self, trace_id: str) -> dict[str, Any] | None:
        path = self._path_for(trace_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _path_for(self, trace_id: str) -> Path:
        safe_trace_id = "".join(char for char in trace_id if char.isalnum() or char in {"-", "_"})
        return self.storage_dir / f"{safe_trace_id}.json"
