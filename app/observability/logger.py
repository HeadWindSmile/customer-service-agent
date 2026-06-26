import json
import logging
from typing import Any


logger = logging.getLogger("customer_service_agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_event(event: str, payload: dict[str, Any], level: str = "info") -> None:
    """统一输出 JSON 日志，便于后续被日志平台或 trace 回放模块采集。"""
    record = {"event": event, **payload}
    message = json.dumps(record, ensure_ascii=False, default=str)
    if level == "error":
        logger.error(message)
    else:
        logger.info(message)

