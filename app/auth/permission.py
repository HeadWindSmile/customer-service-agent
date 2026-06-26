from typing import Any

from app.schemas.chat import ChatRequest


class PermissionDenied(Exception):
    """权限异常由主编排层转换为清晰响应，避免接口层写业务判断。"""


class PermissionChecker:
    """最小 RBAC：普通用户只能查自己，客服可代查但必须产生审计事件。"""

    def resolve_target_user_id(self, request: ChatRequest, slots: dict[str, Any]) -> str:
        target = request.target_user_id or slots.get("target_user_id") or request.user_id
        return str(target).lower()

    def check(self, request: ChatRequest, target_user_id: str) -> dict[str, str] | None:
        caller_user_id = request.user_id.lower()
        if request.role == "user" and target_user_id != caller_user_id:
            raise PermissionDenied("权限不足：普通用户只能查询自己的业务信息。")
        if request.role == "agent":
            return {
                "agent_id": request.user_id,
                "target_user_id": target_user_id,
                "action": "agent_assisted_query",
            }
        return None

