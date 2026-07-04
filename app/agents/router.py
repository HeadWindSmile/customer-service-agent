from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.agents.chains.rag_answer_chain import RagAnswerChain
from app.agents.intent_schema import IntentName
from app.agents.prompts import NO_SOURCE_ANSWER
from app.audit import AuditLogger
from app.auth.context import AuthContext
from app.auth.rbac import ForbiddenError, Permission, PermissionChecker
from app.observability.tracing import add_attribute, add_event, end_span, get_current_trace, start_span
from app.rag.retriever import KnowledgeRetriever
from app.safety.guard import TOOL_PARAM_BLOCKED_ANSWER, SafetyGuard, SafetyViolation
from app.safety.risk_level import SafetyAction
from app.schemas.chat import IntentResult, Source, ToolCall
from app.tools.bill_tool import BillTool
from app.tools.business_client import BusinessClient, BusinessClientError, create_business_client
from app.tools.package_tool import PackageTool
from app.tools.ticket_tool import TicketTool
from app.tools.user_tool import UserTool
from app.utils.time import elapsed_ms


@dataclass
class RouteResult:
    answer: str
    sources: list[Source] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    rewritten_query: str | None = None


RouteHandler = Callable[..., Awaitable[RouteResult]]


class CustomerRouter:
    """注册式 Router。

    第四阶段开始 intent 会持续扩展，注册表比 if/else 更容易看出“新增意图只新增
    handler 和注册项”，避免主分发逻辑随着业务场景增长变成一长串条件判断。
    """

    def __init__(
        self,
        business_client: BusinessClient | None = None,
        permission_checker: PermissionChecker | None = None,
        audit_logger: AuditLogger | None = None,
        safety_guard: SafetyGuard | None = None,
    ) -> None:
        business_client = business_client or create_business_client()
        self.permission_checker = permission_checker or PermissionChecker()
        self.audit_logger = audit_logger or AuditLogger()
        self.safety_guard = safety_guard or SafetyGuard()
        self.retriever = KnowledgeRetriever()
        self.rag_answer_chain = RagAnswerChain()
        self.package_tool = PackageTool(business_client)
        self.bill_tool = BillTool(business_client)
        self.ticket_tool = TicketTool(business_client)
        self.user_tool = UserTool(business_client)
        self.routes: dict[str, RouteHandler] = {
            IntentName.FAQ_QUERY.value: self._handle_faq,
            IntentName.PACKAGE_QUERY.value: self._handle_package_query,
            IntentName.PACKAGE_RECOMMEND.value: self._handle_package_recommend,
            IntentName.PACKAGE_CHANGE.value: self._handle_package_change,
            IntentName.BILL_QUERY.value: self._handle_bill_query,
            IntentName.BILL_EXPLAIN.value: self._handle_bill_explain,
            IntentName.FAULT_DIAGNOSIS.value: self._handle_fault_diagnosis,
            IntentName.NETWORK_REPAIR.value: self._handle_network_repair,
            IntentName.TICKET_CREATE.value: self._handle_ticket_create,
            IntentName.TICKET_QUERY.value: self._handle_ticket_query,
            IntentName.HUMAN_TRANSFER.value: self._handle_human_transfer,
            IntentName.UNKNOWN.value: self._handle_unknown,
        }

    async def route(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]] | None = None,
        memory_summary: str = "",
        key_facts: dict[str, Any] | None = None,
        rewritten_query: str | None = None,
        auth_context: AuthContext | None = None,
        trace_id: str = "",
    ) -> RouteResult:
        auth_context = auth_context or self.permission_checker.build_self_context(user_id)
        effective_user_id = auth_context.effective_user_id
        handler = self.routes.get(intent_result.intent, self._handle_unknown)
        add_event(
            "router.selected",
            {
                "intent": intent_result.intent,
                "handler": getattr(handler, "__name__", "unknown"),
            },
        )
        return await handler(
            intent_result,
            message,
            effective_user_id,
            recent_turns or [],
            memory_summary,
            key_facts or {},
            rewritten_query or message,
            auth_context,
            trace_id,
        )

    async def _handle_faq(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        return self._answer_with_rag(
            message,
            recent_turns,
            scenario="faq",
            memory_summary=memory_summary,
            key_facts=key_facts,
            rewritten_query=rewritten_query,
        )

    async def _handle_package_query(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        permission = self.permission_checker.required_permission(
            auth_context,
            Permission.PACKAGE_QUERY_SELF,
            Permission.PACKAGE_QUERY_AGENT,
        )
        output, call = await self._call_tool(
            "query_user_package",
            {"user_id": user_id},
            lambda: self.package_tool.query_user_package(user_id),
            auth_context=auth_context,
            trace_id=trace_id,
            intent=intent_result.intent,
            required_permission=permission,
            audit_action="package_query",
            resource_type="package",
        )
        if not call.success:
            return RouteResult(answer="套餐查询失败，请稍后再试。", tool_calls=[call], rewritten_query=rewritten_query)
        answer = f"你当前套餐是 {output['package_name']}，月费 {output['monthly_fee']} 元，包含 {output['data_quota']} 流量。"
        return RouteResult(answer=answer, tool_calls=[call], rewritten_query=rewritten_query)

    async def _handle_package_recommend(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        result = self._answer_with_rag(
            message,
            recent_turns,
            scenario="package_recommend",
            memory_summary=memory_summary,
            key_facts=key_facts,
            rewritten_query=rewritten_query,
        )
        if result.sources:
            return result
        return RouteResult(
            answer="我可以先帮你查询当前套餐，再结合流量、通话和预算诉求建议转人工客服确认可办理套餐。",
            rewritten_query=rewritten_query,
        )

    async def _handle_package_change(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        target_package = str(intent_result.slots.get("target_package", "5G畅享套餐"))
        permission = self.permission_checker.required_permission(
            auth_context,
            Permission.PACKAGE_CHANGE_SELF,
            Permission.PACKAGE_CHANGE_AGENT,
        )
        output, call = await self._call_tool(
            "change_package",
            {"user_id": user_id, "target_package": target_package},
            lambda: self.package_tool.change_package(user_id, target_package),
            auth_context=auth_context,
            trace_id=trace_id,
            intent=intent_result.intent,
            required_permission=permission,
            audit_action="package_change",
            resource_type="package",
            audit_metadata={"target_package": target_package},
        )
        if not call.success:
            return RouteResult(answer="套餐办理失败，请稍后再试或转人工客服。", tool_calls=[call], rewritten_query=rewritten_query)
        answer = f"已提交套餐变更申请，目标套餐：{output['target_package']}，单号：{output['order_id']}。"
        return RouteResult(answer=answer, tool_calls=[call], rewritten_query=rewritten_query)

    async def _handle_bill_query(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        month = str(intent_result.slots.get("month", "本月"))
        permission = self.permission_checker.required_permission(
            auth_context,
            Permission.BILL_QUERY_SELF,
            Permission.BILL_QUERY_AGENT,
        )
        output, call = await self._call_tool(
            "query_bill",
            {"user_id": user_id, "month": month},
            lambda: self.bill_tool.query_bill(user_id, month),
            auth_context=auth_context,
            trace_id=trace_id,
            intent=intent_result.intent,
            required_permission=permission,
            audit_action="bill_query",
            resource_type="bill",
            audit_metadata={"month": month},
        )
        if not call.success:
            return RouteResult(answer="账单查询失败，请稍后再试。", tool_calls=[call], rewritten_query=rewritten_query)
        answer = (
            f"{output['month']} 账单金额为 {output['amount']} 元，"
            f"状态：{output['status']}，主要费用项：{', '.join(output['items'])}。"
        )
        return RouteResult(answer=answer, tool_calls=[call], rewritten_query=rewritten_query)

    async def _handle_bill_explain(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        return self._answer_with_rag(
            message,
            recent_turns,
            scenario="bill_explain",
            memory_summary=memory_summary,
            key_facts=key_facts,
            rewritten_query=rewritten_query,
        )

    async def _handle_fault_diagnosis(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        return self._answer_with_rag(
            message,
            recent_turns,
            scenario="fault_diagnosis",
            top_k=2,
            memory_summary=memory_summary,
            key_facts=key_facts,
            rewritten_query=rewritten_query,
        )

    async def _handle_network_repair(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        slots = {**intent_result.slots, "issue_type": "network"}
        permission = self.permission_checker.required_permission(
            auth_context,
            Permission.TICKET_CREATE_SELF,
            Permission.TICKET_CREATE_AGENT,
        )
        output, call = await self._call_tool(
            "create_ticket",
            {"user_id": user_id, "issue_type": "network", "description": message},
            lambda: self.ticket_tool.create_ticket(user_id, "network", message),
            auth_context=auth_context,
            trace_id=trace_id,
            intent=intent_result.intent,
            required_permission=permission,
            audit_action="ticket_create",
            resource_type="ticket",
            audit_metadata={"issue_type": "network"},
        )
        if not call.success:
            return RouteResult(answer="网络报修提交失败，请稍后再试或转人工客服。", tool_calls=[call], rewritten_query=rewritten_query)
        answer = f"已为你提交网络报修工单，工单号：{output['ticket_id']}，当前状态：{output['status']}。"
        intent_result.slots.update(slots)
        return RouteResult(answer=answer, tool_calls=[call], rewritten_query=rewritten_query)

    async def _handle_ticket_create(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        issue_type = str(intent_result.slots.get("issue_type", "general"))
        permission = self.permission_checker.required_permission(
            auth_context,
            Permission.TICKET_CREATE_SELF,
            Permission.TICKET_CREATE_AGENT,
        )
        output, call = await self._call_tool(
            "create_ticket",
            {"user_id": user_id, "issue_type": issue_type, "description": message},
            lambda: self.ticket_tool.create_ticket(user_id, issue_type, message),
            auth_context=auth_context,
            trace_id=trace_id,
            intent=intent_result.intent,
            required_permission=permission,
            audit_action="ticket_create",
            resource_type="ticket",
            audit_metadata={"issue_type": issue_type},
        )
        if not call.success:
            return RouteResult(answer="工单创建失败，请稍后再试。", tool_calls=[call], rewritten_query=rewritten_query)
        answer = f"售后工单已创建，工单号：{output['ticket_id']}，当前状态：{output['status']}。"
        return RouteResult(answer=answer, tool_calls=[call], rewritten_query=rewritten_query)

    async def _handle_ticket_query(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        ticket_id = str(intent_result.slots.get("ticket_id", "")).strip()
        if not ticket_id:
            return RouteResult(answer="请提供需要查询的工单号，我再帮你查看处理进度。", rewritten_query=rewritten_query)
        permission = self.permission_checker.required_permission(
            auth_context,
            Permission.TICKET_QUERY_SELF,
            Permission.TICKET_QUERY_AGENT,
        )
        output, call = await self._call_tool(
            "query_ticket",
            {"user_id": user_id, "ticket_id": ticket_id},
            lambda: self.ticket_tool.query_ticket(user_id, ticket_id),
            auth_context=auth_context,
            trace_id=trace_id,
            intent=intent_result.intent,
            required_permission=permission,
            audit_action="ticket_query",
            resource_type="ticket",
            audit_metadata={"ticket_id": ticket_id},
        )
        if not call.success:
            return RouteResult(answer="工单查询失败，请稍后再试。", tool_calls=[call], rewritten_query=rewritten_query)
        answer = f"工单 {output['ticket_id']} 当前状态：{output['status']}，处理说明：{output['summary']}"
        return RouteResult(answer=answer, tool_calls=[call], rewritten_query=rewritten_query)

    async def _handle_human_transfer(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        return RouteResult(answer="我会为你转接人工客服，请稍候。", rewritten_query=rewritten_query)

    async def _handle_unknown(
        self,
        intent_result: IntentResult,
        message: str,
        user_id: str,
        recent_turns: list[dict[str, str]],
        memory_summary: str,
        key_facts: dict[str, Any],
        rewritten_query: str,
        auth_context: AuthContext,
        trace_id: str,
    ) -> RouteResult:
        return RouteResult(
            answer="我还不能确定你的具体诉求。你可以补充说明是要查套餐、查账单、排查故障还是创建工单。",
            rewritten_query=rewritten_query,
        )

    def _answer_with_rag(
        self,
        message: str,
        recent_turns: list[dict[str, str]],
        scenario: str,
        top_k: int = 3,
        memory_summary: str = "",
        key_facts: dict[str, Any] | None = None,
        rewritten_query: str | None = None,
    ) -> RouteResult:
        search_query = rewritten_query or message
        retrieve_span = start_span("rag.retrieve", {"scenario": scenario, "top_k": top_k})
        sources = self.retriever.search(search_query, top_k=top_k)
        trace = get_current_trace()
        cache_hit = bool(trace.attributes.get("rag_cache_hit")) if trace else False
        retrieval_config = dict(trace.attributes.get("rag_retrieval_config") or {}) if trace else {}
        source_summary = {
            "top_k": top_k,
            "cache_hit": cache_hit,
            "source_count": len(sources),
            "doc_ids": [source.doc_id for source in sources],
            "scores": [source.score for source in sources],
            **retrieval_config,
        }
        add_attribute("rag_retrieval", source_summary)
        add_event("rag.retrieved", source_summary)
        end_span(retrieve_span)
        if not sources:
            return RouteResult(answer=NO_SOURCE_ANSWER, rewritten_query=search_query)
        answer_span = start_span("rag.answer", {"scenario": scenario, "source_count": len(sources)})
        answer = self.rag_answer_chain.generate(
            question=search_query,
            sources=sources,
            conversation_context=recent_turns,
            conversation_summary=memory_summary,
            key_facts=key_facts or {},
            scenario=scenario,
        )
        end_span(answer_span)
        return RouteResult(answer=answer, sources=sources, rewritten_query=search_query)

    async def _call_tool(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        func: Callable[[], Awaitable[dict[str, Any]]],
        *,
        auth_context: AuthContext | None = None,
        trace_id: str = "",
        intent: str = "",
        required_permission: Permission | None = None,
        audit_action: str = "",
        resource_type: str = "business",
        audit_metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ToolCall]:
        permission_value = required_permission.value if required_permission else None
        tool_span = start_span(
            "tool.call",
            {
                "tool_name": tool_name,
                "permission": permission_value,
                "intent": intent,
            },
        )
        started = elapsed_ms()
        permission_checked = False

        try:
            if auth_context and required_permission:
                try:
                    self.permission_checker.require(auth_context, required_permission)
                    permission_checked = True
                except ForbiddenError as exc:
                    denied_audit_logged = self.audit_logger.log_tool_action(
                        trace_id=trace_id,
                        auth_context=auth_context,
                        action=audit_action or tool_name,
                        permission=required_permission.value,
                        intent=intent,
                        tool_name=tool_name,
                        resource_type=resource_type,
                        allowed=False,
                        success=False,
                        reason=str(exc),
                        metadata=audit_metadata or {},
                    )
                    add_event(
                        "tool.permission_denied",
                        {
                            "tool_name": tool_name,
                            "permission": permission_value,
                            "audit_logged": denied_audit_logged,
                        },
                    )
                    raise

            tool_safety = self.safety_guard.scan_tool_params(input_data, trace_id=trace_id)
            add_event(
                "tool.safety_checked",
                {
                    "tool_name": tool_name,
                    "risk_level": tool_safety.risk_level.value,
                    "action": tool_safety.action.value,
                    "finding_count": len(tool_safety.findings),
                    "review_queued": tool_safety.review_queued,
                },
            )
            if tool_safety.action != SafetyAction.ALLOW:
                raise SafetyViolation(TOOL_PARAM_BLOCKED_ANSWER, tool_safety)

            try:
                output = await func()
                success = True
                error_message = None
            except BusinessClientError as exc:
                output = exc.to_output()
                success = False
                error_message = exc.message
            except Exception as exc:
                output = {"error_code": "TOOL_CALL_FAILED", "message": str(exc)}
                success = False
                error_message = str(exc)

            audit_logged = False
            if auth_context and required_permission and self.permission_checker.should_audit(auth_context, required_permission):
                audit_logged = self.audit_logger.log_tool_action(
                    trace_id=trace_id,
                    auth_context=auth_context,
                    action=audit_action or tool_name,
                    permission=required_permission.value,
                    intent=intent,
                    tool_name=tool_name,
                    resource_type=resource_type,
                    allowed=True,
                    success=success,
                    reason=error_message or "",
                    metadata={**(audit_metadata or {}), **_audit_metadata_from_output(output)},
                )

            call = ToolCall(
                tool_name=tool_name,
                input=self.safety_guard.sanitize_tool_payload(input_data),
                output=self.safety_guard.sanitize_tool_payload(output),
                success=success,
                latency_ms=elapsed_ms() - started,
                error_message=error_message,
                permission=permission_value,
                permission_checked=permission_checked,
                audit_logged=audit_logged,
            )
            tool_result = {
                "tool_name": tool_name,
                "success": success,
                "latency_ms": call.latency_ms,
                "permission": permission_value,
                "permission_checked": permission_checked,
                "audit_logged": audit_logged,
            }
            if error_message:
                tool_result["error_message"] = error_message
            add_event("tool.called", tool_result)
            return output, call
        finally:
            end_span(tool_span)


def _audit_metadata_from_output(output: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("status", "order_id", "ticket_id", "issue_type", "month", "target_package", "error_code"):
        if output.get(key) is not None:
            metadata[key] = output[key]
    return metadata
