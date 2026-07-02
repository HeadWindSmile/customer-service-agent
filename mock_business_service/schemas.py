from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    error_code: str
    message: str


class UserProfileResponse(BaseModel):
    user_id: str
    name: str
    level: str


class PackageResponse(BaseModel):
    package_name: str
    monthly_fee: float
    data_quota: str


class BillResponse(BaseModel):
    month: str
    amount: float
    status: str
    items: list[str]


class PackageChangeRequest(BaseModel):
    target_package: str = Field(..., min_length=1)


class PackageChangeResponse(BaseModel):
    order_id: str
    user_id: str
    target_package: str
    status: str


class TicketCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    issue_type: str = Field(default="general", min_length=1)
    description: str = Field(..., min_length=1)


class TicketResponse(BaseModel):
    ticket_id: str
    user_id: str
    issue_type: str
    description: str = ""
    status: str
    summary: str = ""
