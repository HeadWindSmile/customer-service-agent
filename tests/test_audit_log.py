import asyncio
import json

from app.agents.customer_agent import CustomerAgent
from app.agents.router import CustomerRouter
from app.audit import AuditLogger
from app.auth.context import AuthContext
from app.schemas.chat import ChatRequest


def _agent_with_audit_log(log_path) -> CustomerAgent:
    agent = CustomerAgent()
    audit_logger = AuditLogger(log_path=str(log_path), enabled=True)
    agent.router = CustomerRouter(permission_checker=agent.permission_checker, audit_logger=audit_logger)
    return agent


def test_agent_bill_query_writes_masked_audit_log(tmp_path):
    async def scenario():
        log_path = tmp_path / "audit.log"
        agent = _agent_with_audit_log(log_path)
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="audit-agent-bill",
                role="agent",
                target_user_id="u1002",
                message="帮客户查本月账单",
            )
        )

        assert response.error is None
        assert response.tool_calls[0].audit_logged is True
        content = log_path.read_text(encoding="utf-8")
        record = json.loads(content.strip().splitlines()[-1])
        assert record["event"] == "audit.tool_action"
        assert record["action"] == "bill_query"
        assert record["permission"] == "BILL_QUERY_AGENT"
        assert record["allowed"] is True
        assert record["success"] is True
        assert "u1002" not in content
        assert record["target_user_id_masked"] == "u***2"

    asyncio.run(scenario())


def test_audit_logger_sanitizes_sensitive_metadata(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(log_path=str(log_path), enabled=True)
    auth_context = AuthContext(
        current_user_id="agent001",
        role="agent",
        target_user_id="u1002",
        permissions=frozenset({"BILL_QUERY_AGENT"}),
    )

    logged = logger.log_tool_action(
        trace_id="trace-test",
        auth_context=auth_context,
        action="bill_query",
        permission="BILL_QUERY_AGENT",
        intent="bill_query",
        tool_name="query_bill",
        resource_type="bill",
        allowed=True,
        success=True,
        metadata={"message": "手机号13812345678，身份证110101199001011234"},
    )

    assert logged is True
    content = log_path.read_text(encoding="utf-8")
    assert "13812345678" not in content
    assert "110101199001011234" not in content
    assert "138****5678" in content
    assert "身份证号已脱敏" in content
