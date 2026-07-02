from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.agents.chains.rag_answer_chain import RagAnswerChain
from app.agents.intent_schema import IntentName
from app.agents.prompts import NO_SOURCE_ANSWER
from app.rag.retriever import KnowledgeRetriever
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

    def __init__(self, business_client: BusinessClient | None = None) -> None:
        business_client = business_client or create_business_client()
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
    ) -> RouteResult:
        handler = self.routes.get(intent_result.intent, self._handle_unknown)
        return await handler(
            intent_result,
            message,
            user_id,
            recent_turns or [],
            memory_summary,
            key_facts or {},
            rewritten_query or message,
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
    ) -> RouteResult:
        output, call = await self._call_tool(
            "query_user_package",
            {"user_id": user_id},
            lambda: self.package_tool.query_user_package(user_id),
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
    ) -> RouteResult:
        target_package = str(intent_result.slots.get("target_package", "5G畅享套餐"))
        output, call = await self._call_tool(
            "change_package",
            {"user_id": user_id, "target_package": target_package},
            lambda: self.package_tool.change_package(user_id, target_package),
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
    ) -> RouteResult:
        month = str(intent_result.slots.get("month", "本月"))
        output, call = await self._call_tool(
            "query_bill",
            {"user_id": user_id, "month": month},
            lambda: self.bill_tool.query_bill(user_id, month),
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
    ) -> RouteResult:
        slots = {**intent_result.slots, "issue_type": "network"}
        output, call = await self._call_tool(
            "create_ticket",
            {"user_id": user_id, "issue_type": "network", "description": message},
            lambda: self.ticket_tool.create_ticket(user_id, "network", message),
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
    ) -> RouteResult:
        issue_type = str(intent_result.slots.get("issue_type", "general"))
        output, call = await self._call_tool(
            "create_ticket",
            {"user_id": user_id, "issue_type": issue_type, "description": message},
            lambda: self.ticket_tool.create_ticket(user_id, issue_type, message),
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
    ) -> RouteResult:
        ticket_id = str(intent_result.slots.get("ticket_id", "")).strip()
        if not ticket_id:
            return RouteResult(answer="请提供需要查询的工单号，我再帮你查看处理进度。", rewritten_query=rewritten_query)
        output, call = await self._call_tool(
            "query_ticket",
            {"user_id": user_id, "ticket_id": ticket_id},
            lambda: self.ticket_tool.query_ticket(user_id, ticket_id),
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
        sources = self.retriever.search(search_query, top_k=top_k)
        if not sources:
            return RouteResult(answer=NO_SOURCE_ANSWER, rewritten_query=search_query)
        answer = self.rag_answer_chain.generate(
            question=search_query,
            sources=sources,
            conversation_context=recent_turns,
            conversation_summary=memory_summary,
            key_facts=key_facts or {},
            scenario=scenario,
        )
        return RouteResult(answer=answer, sources=sources, rewritten_query=search_query)

    async def _call_tool(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        func: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], ToolCall]:
        started = elapsed_ms()
        try:
            output = await func()
            call = ToolCall(
                tool_name=tool_name,
                input=input_data,
                output=output,
                success=True,
                latency_ms=elapsed_ms() - started,
            )
            return output, call
        except BusinessClientError as exc:
            output = exc.to_output()
            call = ToolCall(
                tool_name=tool_name,
                input=input_data,
                output=output,
                success=False,
                latency_ms=elapsed_ms() - started,
                error_message=exc.message,
            )
            return output, call
        except Exception as exc:
            output = {"error_code": "TOOL_CALL_FAILED", "message": str(exc)}
            call = ToolCall(
                tool_name=tool_name,
                input=input_data,
                output=output,
                success=False,
                latency_ms=elapsed_ms() - started,
                error_message=str(exc),
            )
            return output, call
