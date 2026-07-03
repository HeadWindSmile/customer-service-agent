from fastapi import FastAPI, HTTPException, Query

from mock_business_service import data
from mock_business_service.schemas import (
    BillResponse,
    ErrorDetail,
    PackageChangeRequest,
    PackageChangeResponse,
    PackageResponse,
    TicketCreateRequest,
    TicketResponse,
    UserProfileResponse,
)


app = FastAPI(
    title="Mock Business Service",
    version="0.1.0",
    description="模拟原有 Java/Spring Boot 业务系统的内部 HTTP API。",
)


@app.get("/health")
def health() -> dict:
    """给 Docker Compose 和 AI 服务 readiness 使用的轻量存活检查。"""

    return {"status": "ok", "service": "mock-business-service"}


def _business_error(status_code: int, error_code: str, message: str) -> None:
    # 统一错误结构，便于 AI 服务把业务失败写入 tool_calls，而不是暴露框架异常。
    detail = ErrorDetail(error_code=error_code, message=message).model_dump()
    raise HTTPException(status_code=status_code, detail=detail)


@app.get("/internal/users/{user_id}", response_model=UserProfileResponse)
def get_user(user_id: str) -> dict:
    user = data.get_user(user_id)
    if not user:
        _business_error(404, "USER_NOT_FOUND", "用户不存在。")
    return user


@app.get("/internal/users/{user_id}/package", response_model=PackageResponse)
def get_user_package(user_id: str) -> dict:
    if not data.get_user(user_id):
        _business_error(404, "USER_NOT_FOUND", "用户不存在。")
    package = data.get_user_package(user_id)
    if not package:
        _business_error(404, "PACKAGE_NOT_FOUND", "用户当前套餐不存在。")
    return package


@app.get("/internal/users/{user_id}/bill", response_model=BillResponse)
def get_user_bill(user_id: str, month: str = Query(default="本月")) -> dict:
    if not data.get_user(user_id):
        _business_error(404, "USER_NOT_FOUND", "用户不存在。")
    bill = data.get_bill(user_id, month)
    if not bill:
        _business_error(404, "BILL_NOT_FOUND", "账单不存在。")
    return bill


@app.post("/internal/users/{user_id}/package/change", response_model=PackageChangeResponse)
def change_package(user_id: str, request: PackageChangeRequest) -> dict:
    if not data.get_user(user_id):
        _business_error(404, "USER_NOT_FOUND", "用户不存在。")
    if request.target_package not in data.AVAILABLE_PACKAGES:
        _business_error(404, "TARGET_PACKAGE_NOT_FOUND", "目标套餐不存在。")
    return data.change_user_package(user_id, request.target_package)


@app.post("/internal/tickets", response_model=TicketResponse)
def create_ticket(request: TicketCreateRequest) -> dict:
    if not data.get_user(request.user_id):
        _business_error(404, "USER_NOT_FOUND", "用户不存在。")
    if request.issue_type == "fail_create" or "模拟失败" in request.description:
        _business_error(500, "TICKET_CREATE_FAILED", "工单创建失败。")
    return data.create_ticket(request.user_id, request.issue_type, request.description)


@app.get("/internal/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str) -> dict:
    ticket = data.get_ticket(ticket_id)
    if not ticket:
        _business_error(404, "TICKET_NOT_FOUND", "工单不存在。")
    return ticket
