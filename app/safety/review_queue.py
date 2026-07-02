import json
import os
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.observability.logger import log_event
from app.safety.risk_level import SafetyResult
from app.safety.sanitizer import sanitize_text


class ReviewQueue:
    """本地人工审核队列。

    第 8 阶段只写 JSON Lines，既能演示高危内容留痕，又避免提前实现第 9 阶段
    RocketMQ 或复杂审核后台。
    """

    def __init__(self, log_path: str | None = None) -> None:
        self.log_path = log_path or settings.safety_review_queue_path

    def enqueue(
        self,
        *,
        trace_id: str,
        result: SafetyResult,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if not result.should_review:
            return False
        record = {
            "trace_id": trace_id,
            "risk_type": ",".join(sorted({finding.risk_type for finding in result.findings})),
            "risk_level": result.risk_level.value,
            "scope": result.scope,
            "content_masked": sanitize_text(content[:500]),
            "findings": [finding.to_dict() for finding in result.findings],
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            parent = os.path.dirname(self.log_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            log_event("safety.review_queued", {"trace_id": trace_id, "risk_level": result.risk_level.value, "scope": result.scope})
            return True
        except Exception as exc:
            log_event("safety.review_queue_failed", {"trace_id": trace_id, "error": str(exc)}, level="error")
            return False
