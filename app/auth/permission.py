from app.auth.rbac import ForbiddenError, Permission, PermissionChecker, Role


# 兼容旧名称：第 7 阶段统一使用 ForbiddenError，但保留旧 import 不破坏历史代码。
PermissionDenied = ForbiddenError


__all__ = ["ForbiddenError", "Permission", "PermissionChecker", "PermissionDenied", "Role"]
