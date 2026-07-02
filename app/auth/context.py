from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthContext:
    """一次请求的授权上下文。

    权限判断需要同时知道“当前登录人”和“实际被操作的客户”。把这些信息收敛成
    AuthContext，可以避免 role、target_user_id 在 Router 和工具调用之间反复散传。
    """

    current_user_id: str
    role: str
    target_user_id: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    request_target_user_id: str | None = None
    slot_target_user_id: str | None = None

    @property
    def effective_user_id(self) -> str:
        """业务工具实际访问的用户 ID；未指定目标用户时回落到当前用户。"""

        return self.target_user_id or self.current_user_id

    @property
    def is_agent_acting_for_user(self) -> bool:
        """是否属于客服/管理员代用户操作。"""

        return self.role in {"agent", "admin"} and bool(self.target_user_id)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def to_trace_attributes(self) -> dict[str, object]:
        return {
            "auth_role": self.role,
            "auth_current_user_id_masked": mask_identifier(self.current_user_id),
            "auth_target_user_id_masked": mask_identifier(self.target_user_id),
            "auth_permissions": sorted(self.permissions),
            "auth_is_agent_acting_for_user": self.is_agent_acting_for_user,
        }


def mask_identifier(value: str | None) -> str | None:
    """日志中的用户标识只保留少量可排查信息，避免审计/trace 泄露完整 ID。"""

    if value is None:
        return None
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    if len(text) <= 6:
        return f"{text[0]}***{text[-1]}"
    return f"{text[:2]}***{text[-2:]}"
