from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.agents.prompts import FAQ_ANSWER_TEMPLATE, NO_SOURCE_ANSWER
from app.rag.retriever import MockKnowledgeRetriever
from app.schemas.chat import IntentResult, Source, ToolCall
from app.tools.bill_tool import BillTool
from app.tools.business_client import MockBusinessClient
from app.tools.package_tool import PackageTool
from app.tools.ticket_tool import TicketTool
from app.tools.user_tool import UserTool
from app.utils.time import elapsed_ms


@dataclass
class RouteResult:
    answer: str
    sources: list[Source] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)


class CustomerRouter:
    """Router 只按 intent 分发，避免主编排层了解每个业务工具的细节。"""

    def __init__(self) -> None:
        business_client = MockBusinessClient()
        self.retriever = MockKnowledgeRetriever()
        self.package_tool = PackageTool(business_client)
        self.bill_tool = BillTool(business_client)
        self.ticket_tool = TicketTool(business_client)
        self.user_tool = UserTool(business_client)

    def route(self, intent_result: IntentResult, message: str, user_id: str) -> RouteResult:
        intent = intent_result.intent
        slots = intent_result.slots
        if intent == "faq_query":
            return self._handle_faq(message)
        if intent == "package_query":
            return self._handle_package_query(user_id)
        if intent == "package_change":
            return self._handle_package_change(user_id, slots)
        if intent == "bill_query":
            return self._handle_bill_query(user_id, slots)
        if intent == "fault_diagnosis":
            return self._handle_fault_diagnosis(message)
        if intent == "ticket_create":
            return self._handle_ticket_create(user_id, slots, message)
        return RouteResult(answer="暂时无法识别你的问题，建议转人工客服。")

    def _handle_faq(self, message: str) -> RouteResult:
        sources = self.retriever.search(message, top_k=3)
        if not sources:
            return RouteResult(answer=NO_SOURCE_ANSWER)
        top_source = sources[0]
        answer = FAQ_ANSWER_TEMPLATE.format(title=top_source.title, content=top_source.content)
        return RouteResult(answer=answer, sources=sources)

    def _handle_package_query(self, user_id: str) -> RouteResult:
        output, call = self._call_tool(
            "query_user_package",
            {"user_id": user_id},
            lambda: self.package_tool.query_user_package(user_id),
        )
        if not call.success:
            return RouteResult(answer="套餐查询失败，请稍后再试。", tool_calls=[call])
        answer = f"你当前套餐是 {output['package_name']}，月费 {output['monthly_fee']} 元，包含 {output['data_quota']} 流量。"
        return RouteResult(answer=answer, tool_calls=[call])

    def _handle_bill_query(self, user_id: str, slots: dict[str, Any]) -> RouteResult:
        month = str(slots.get("month", "本月"))
        output, call = self._call_tool(
            "query_bill",
            {"user_id": user_id, "month": month},
            lambda: self.bill_tool.query_bill(user_id, month),
        )
        if not call.success:
            return RouteResult(answer="账单查询失败，请稍后再试。", tool_calls=[call])
        answer = (
            f"{output['month']} 账单金额为 {output['amount']} 元，"
            f"状态：{output['status']}，主要费用项：{', '.join(output['items'])}。"
        )
        return RouteResult(answer=answer, tool_calls=[call])

    def _handle_package_change(self, user_id: str, slots: dict[str, Any]) -> RouteResult:
        target_package = str(slots.get("target_package", "5G畅享套餐"))
        output, call = self._call_tool(
            "change_package",
            {"user_id": user_id, "target_package": target_package},
            lambda: self.package_tool.change_package(user_id, target_package),
        )
        if not call.success:
            return RouteResult(answer="套餐办理失败，请稍后再试或转人工客服。", tool_calls=[call])
        answer = f"已提交套餐变更申请，目标套餐：{output['target_package']}，单号：{output['order_id']}。"
        return RouteResult(answer=answer, tool_calls=[call])

    def _handle_fault_diagnosis(self, message: str) -> RouteResult:
        sources = self.retriever.search(message, top_k=2)
        answer = (
            "建议先按以下步骤排查：1. 重启光猫和路由器；2. 检查光猫指示灯；"
            "3. 确认是否存在欠费停机；4. 如果仍未恢复，可创建售后工单。"
        )
        if sources:
            answer = f"{answer}\n参考知识库：{sources[0].title}。"
        return RouteResult(answer=answer, sources=sources)

    def _handle_ticket_create(self, user_id: str, slots: dict[str, Any], message: str) -> RouteResult:
        issue_type = str(slots.get("issue_type", "general"))
        output, call = self._call_tool(
            "create_ticket",
            {"user_id": user_id, "issue_type": issue_type, "description": message},
            lambda: self.ticket_tool.create_ticket(user_id, issue_type, message),
        )
        if not call.success:
            return RouteResult(answer="工单创建失败，请稍后再试。", tool_calls=[call])
        answer = f"售后工单已创建，工单号：{output['ticket_id']}，当前状态：{output['status']}。"
        return RouteResult(answer=answer, tool_calls=[call])

    def _call_tool(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        func: Callable[[], dict[str, Any]],
    ) -> tuple[dict[str, Any], ToolCall]:
        started = elapsed_ms()
        try:
            output = func()
            call = ToolCall(
                tool_name=tool_name,
                input=input_data,
                output=output,
                success=True,
                latency_ms=elapsed_ms() - started,
            )
            return output, call
        except Exception as exc:
            output = {"error": str(exc)}
            call = ToolCall(
                tool_name=tool_name,
                input=input_data,
                output=output,
                success=False,
                latency_ms=elapsed_ms() - started,
            )
            return output, call

