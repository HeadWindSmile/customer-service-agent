from typing import Any

from fastapi import APIRouter, HTTPException

from app.observability.trace_repository import TraceRepository


router = APIRouter(prefix="/api", tags=["traces"])
trace_repository = TraceRepository()


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    """本地 trace 回放接口。

    API 层只负责读取和返回，不解释 trace 语义；链路含义仍由 observability
    层的 schema 和 CustomerAgent 编排逻辑共同维护。
    """

    trace = trace_repository.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace 不存在")
    return trace
