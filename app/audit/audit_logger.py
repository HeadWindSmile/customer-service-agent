import json
import os
from datetime import datetime, timezone
from typing import Any

from app.auth.context import AuthContext, mask_identifier
from app.config import settings
from app.memory.privacy import sanitize_text
from app.observability.logger import log_event


class AuditLogger:
    """结构化审计日志。

    第 7 阶段只写本地 JSON Lines 文件，既能演示企业审计链路，又避免提前引入
    RocketMQ 或数据库。后续第 9 阶段可以把这里的 record 原样发布为异步事件。
    """

    def __init__(self, log_path: str | None = None, enabled: bool | None = None) -> None:
        self.log_path = log_path or settings.audit_log_path
        self.enabled = settings.audit_log_enabled if enabled is None else enabled
        # 保留已写入记录的短暂内存副本，方便编排层在不耦合审计模块和 MQ 的前提下发布事件。
        self._written_records: list[dict[str, Any]] = []

    def log_tool_action(
        self,
        *,
        trace_id: str,
        auth_context: AuthContext,
        action: str,
        permission: str,
        intent: str,
        tool_name: str,
        resource_type: str,
        allowed: bool,
        success: bool,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if not self.enabled:
            return False

        record = {
            "event": "audit.tool_action",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "role": auth_context.role,
            "actor_user_id_masked": mask_identifier(auth_context.current_user_id),
            "target_user_id_masked": mask_identifier(auth_context.target_user_id),
            "action": action,
            "permission": permission,
            "intent": intent,
            "tool_name": tool_name,
            "resource_type": resource_type,
            "allowed": allowed,
            "success": success,
            "reason": sanitize_text(reason),
            "metadata": _sanitize_value(metadata or {}),
        }
        return self._write(record)

    def _write(self, record: dict[str, Any]) -> bool:
        try:
            parent = os.path.dirname(self.log_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            self._written_records.append(record)
            log_event(
                "audit.logged",
                {
                    "trace_id": record.get("trace_id"),
                    "action": record.get("action"),
                    "permission": record.get("permission"),
                    "allowed": record.get("allowed"),
                    "success": record.get("success"),
                },
            )
            return True
        except Exception as exc:
            # 审计写入失败不能拖垮客服主链路；真实生产可在这里接入备用队列。
            log_event("audit.write_failed", {"error": str(exc)}, level="error")
            return False

    def drain_records(self, trace_id: str) -> list[dict[str, Any]]:
        """取出指定 trace 的审计记录。

        审计模块仍然只负责写审计日志；事件发布由 CustomerAgent 读取这些已落盘记录后完成，
        避免 audit 层直接依赖 event schema 或 RocketMQ producer。
        """

        matched = [record for record in self._written_records if record.get("trace_id") == trace_id]
        self._written_records = [record for record in self._written_records if record.get("trace_id") != trace_id]
        return matched


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value[:200])
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in {"description", "message", "raw_input", "raw_output"}:
                sanitized[key] = sanitize_text(str(item)[:120])
                continue
            sanitized[key] = _sanitize_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:20]]
    return value
