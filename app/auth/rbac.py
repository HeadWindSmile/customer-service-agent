from enum import Enum
from typing import Any

from app.auth.context import AuthContext
from app.schemas.chat import ChatRequest


class ForbiddenError(Exception):
    """越权异常由主编排层转换为标准响应，API 层不写业务权限逻辑。"""


class Role(str, Enum):
    USER = "user"
    AGENT = "agent"
    ADMIN = "admin"


class Permission(str, Enum):
    FAQ_QUERY = "FAQ_QUERY"
    PACKAGE_QUERY_SELF = "PACKAGE_QUERY_SELF"
    PACKAGE_QUERY_AGENT = "PACKAGE_QUERY_AGENT"
    BILL_QUERY_SELF = "BILL_QUERY_SELF"
    BILL_QUERY_AGENT = "BILL_QUERY_AGENT"
    PACKAGE_CHANGE_SELF = "PACKAGE_CHANGE_SELF"
    PACKAGE_CHANGE_AGENT = "PACKAGE_CHANGE_AGENT"
    TICKET_CREATE_SELF = "TICKET_CREATE_SELF"
    TICKET_CREATE_AGENT = "TICKET_CREATE_AGENT"
    TICKET_QUERY_SELF = "TICKET_QUERY_SELF"
    TICKET_QUERY_AGENT = "TICKET_QUERY_AGENT"
    OFFER_QUERY_SELF = "OFFER_QUERY_SELF"
    OFFER_QUERY_AGENT = "OFFER_QUERY_AGENT"
    OFFER_RECOMMEND_SELF = "OFFER_RECOMMEND_SELF"
    OFFER_RECOMMEND_AGENT = "OFFER_RECOMMEND_AGENT"
    ORDER_QUERY_SELF = "ORDER_QUERY_SELF"
    ORDER_QUERY_AGENT = "ORDER_QUERY_AGENT"


ALL_PERMISSIONS = frozenset(permission.value for permission in Permission)

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.USER: frozenset(
        {
            Permission.FAQ_QUERY.value,
            Permission.PACKAGE_QUERY_SELF.value,
            Permission.BILL_QUERY_SELF.value,
            Permission.PACKAGE_CHANGE_SELF.value,
            Permission.TICKET_CREATE_SELF.value,
            Permission.TICKET_QUERY_SELF.value,
            Permission.OFFER_QUERY_SELF.value,
            Permission.OFFER_RECOMMEND_SELF.value,
            Permission.ORDER_QUERY_SELF.value,
        }
    ),
    # 客服可代查与代建工单；套餐变更属于更高风险操作，本阶段默认只给 admin。
    Role.AGENT: frozenset(
        {
            Permission.FAQ_QUERY.value,
            Permission.PACKAGE_QUERY_AGENT.value,
            Permission.BILL_QUERY_AGENT.value,
            Permission.TICKET_CREATE_AGENT.value,
            Permission.TICKET_QUERY_AGENT.value,
            Permission.OFFER_QUERY_AGENT.value,
            Permission.OFFER_RECOMMEND_AGENT.value,
            Permission.ORDER_QUERY_AGENT.value,
        }
    ),
    Role.ADMIN: ALL_PERMISSIONS,
}

SENSITIVE_PERMISSIONS = frozenset(
    {
        Permission.PACKAGE_QUERY_AGENT.value,
        Permission.BILL_QUERY_SELF.value,
        Permission.BILL_QUERY_AGENT.value,
        Permission.PACKAGE_CHANGE_SELF.value,
        Permission.PACKAGE_CHANGE_AGENT.value,
        Permission.TICKET_CREATE_SELF.value,
        Permission.TICKET_CREATE_AGENT.value,
        Permission.TICKET_QUERY_SELF.value,
        Permission.TICKET_QUERY_AGENT.value,
        Permission.OFFER_QUERY_AGENT.value,
        Permission.OFFER_RECOMMEND_AGENT.value,
        Permission.ORDER_QUERY_SELF.value,
        Permission.ORDER_QUERY_AGENT.value,
    }
)


class PermissionChecker:
    """企业级 RBAC 校验器。

    第 7 阶段不接真实权限中心，而是用内存映射表达角色与权限关系。这样既能保证
    本地 demo 可运行，也能在面试中讲清未来如何替换为企业 IAM/RBAC 服务。
    """

    def build_context(self, request: ChatRequest, slots: dict[str, Any]) -> AuthContext:
        role = Role(request.role)
        current_user_id = _normalize_user_id(request.user_id)
        request_target = _normalize_optional_user_id(request.target_user_id)
        slot_target = _normalize_optional_user_id(slots.get("target_user_id"))

        if request_target and slot_target and request_target != slot_target:
            raise ForbiddenError("权限不足：请求目标用户与问题中的目标用户不一致。")

        target_user_id = request_target or slot_target
        if role == Role.USER:
            target_user_id = target_user_id or current_user_id
            if target_user_id != current_user_id:
                raise ForbiddenError("权限不足：普通用户只能访问自己的业务信息。")

        return AuthContext(
            current_user_id=current_user_id,
            role=role.value,
            target_user_id=target_user_id,
            permissions=ROLE_PERMISSIONS[role],
            request_target_user_id=request_target,
            slot_target_user_id=slot_target,
        )

    def build_self_context(self, user_id: str, role: Role = Role.USER) -> AuthContext:
        normalized_user_id = _normalize_user_id(user_id)
        return AuthContext(
            current_user_id=normalized_user_id,
            role=role.value,
            target_user_id=normalized_user_id,
            permissions=ROLE_PERMISSIONS[role],
        )

    def required_permission(
        self,
        auth_context: AuthContext,
        self_permission: Permission,
        agent_permission: Permission,
    ) -> Permission:
        if auth_context.role == Role.USER.value:
            return self_permission
        if auth_context.role == Role.AGENT.value:
            return agent_permission
        if auth_context.target_user_id and auth_context.target_user_id != auth_context.current_user_id:
            return agent_permission
        return self_permission

    def require(self, auth_context: AuthContext, permission: Permission) -> None:
        permission_value = permission.value
        if auth_context.role == Role.AGENT.value and permission_value.endswith("_AGENT"):
            if not auth_context.target_user_id:
                raise ForbiddenError("权限不足：客服代查或代办业务时必须提供 target_user_id。")
        if not auth_context.has_permission(permission_value):
            raise ForbiddenError(f"权限不足：当前角色缺少 {permission_value} 权限。")

    def should_audit(self, auth_context: AuthContext, permission: Permission) -> bool:
        permission_value = permission.value
        return auth_context.is_agent_acting_for_user or permission_value in SENSITIVE_PERMISSIONS


def _normalize_user_id(user_id: Any) -> str:
    return str(user_id).strip().lower()


def _normalize_optional_user_id(user_id: Any) -> str | None:
    if user_id is None:
        return None
    normalized = str(user_id).strip().lower()
    return normalized or None
