from app.agents.intent_classifier import IntentClassifier
from app.agents.prompts import LOW_CONFIDENCE_ANSWER
from app.agents.query_rewriter import QueryRewriter
from app.agents.router import CustomerRouter, RouteResult
from app.auth.context import mask_identifier
from app.auth.rbac import ForbiddenError, PermissionChecker
from app.config import settings
from app.events import EventBus
from app.events.event_type import EventType
from app.memory.factory import create_memory_store
from app.memory.manager import ConversationMemoryManager
from app.observability.logger import log_event
from app.observability.trace_repository import TraceRepository
from app.observability.tracing import TraceContext, add_event, get_current_trace, reset_current_trace, set_current_trace
from app.safety.guard import INPUT_BLOCKED_ANSWER, INPUT_REVIEW_ANSWER, OUTPUT_BLOCKED_ANSWER, SafetyGuard, SafetyViolation
from app.safety.risk_level import SafetyAction, SafetyResult
from app.schemas.chat import ChatRequest, ChatResponse
from app.utils.time import elapsed_ms


class CustomerAgent:
    """主编排层串起权限、安全、意图、路由、记忆和观测，方便面试时讲清主链路。"""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.intent_classifier = IntentClassifier()
        self.memory = ConversationMemoryManager(create_memory_store())
        self.query_rewriter = QueryRewriter()
        self.safety_guard = SafetyGuard()
        self.router = CustomerRouter(safety_guard=self.safety_guard)
        self.permission_checker = PermissionChecker()
        self.event_bus = event_bus or EventBus()
        self.trace_repository = TraceRepository()

    async def handle(self, request: ChatRequest) -> ChatResponse:
        trace = TraceContext.new()
        trace_token = set_current_trace(trace)
        trace.start_span(
            "chat.handle",
            {
                "role": request.role,
                "session_id": request.session_id,
                "user_id_masked": mask_identifier(request.user_id),
            },
        )
        trace.add_attribute("trace_id", trace.trace_id)
        trace.add_attribute("user_id_masked", mask_identifier(request.user_id))
        trace.add_attribute("session_id", request.session_id)
        trace.add_attribute("role", request.role)
        trace.add_attribute("intent", "unknown")
        trace.add_attribute("slots", {})
        trace.add_attribute("confidence", 0.0)
        trace.add_attribute("tool_calls", [])
        trace.add_attribute("retrieved_sources", [])
        trace.add_attribute("event_publish_result", [])
        trace.add_attribute("llm_provider", None)
        trace.add_attribute("model_name", None)
        trace.add_attribute("prompt_tokens", 0)
        trace.add_attribute("completion_tokens", 0)
        trace.add_attribute("total_tokens", 0)
        trace.add_attribute("estimated_cost", 0.0)
        trace.add_event("chat.received", {"message_length": len(request.message)})
        intent = "unknown"
        slots: dict[str, object] = {}
        confidence = 0.0
        intent_reason = ""
        rewritten_query: str | None = None
        input_safety: SafetyResult | None = None
        output_safety: SafetyResult | None = None
        try:
            input_span = trace.start_span("safety.input")
            input_safety = self.safety_guard.scan_input(request.message, trace_id=trace.trace_id)
            trace.end_span(input_span)
            trace.add_attribute("input_safety", input_safety.to_dict())
            if input_safety.action != SafetyAction.ALLOW:
                answer = INPUT_BLOCKED_ANSWER if input_safety.action == SafetyAction.BLOCK else INPUT_REVIEW_ANSWER
                error = "SAFETY_INPUT_BLOCKED" if input_safety.action == SafetyAction.BLOCK else "SAFETY_REVIEW_REQUIRED"
                trace.add_attribute("error", error)
                log_event("chat.safety_blocked", trace.to_log_payload())
                await self._publish_safety_review_if_needed(request, trace.trace_id, input_safety)
                response = ChatResponse(
                    answer=answer,
                    intent=intent,
                    slots=slots,
                    confidence=confidence,
                    intent_reason=intent_reason,
                    sources=[],
                    tool_calls=[],
                    trace_id=trace.trace_id,
                    latency_ms=trace.latency_ms,
                    error=error,
                    rewritten_query=rewritten_query,
                    safety_result={"input_safety": input_safety.to_dict()},
                )
                await self._publish_chat_finished(request, response, input_safety, output_safety)
                return response

            memory_span = trace.start_span("memory.load")
            memory_started = elapsed_ms()
            memory_context = await self.memory.load_context(request.user_id, request.session_id)
            trace.end_span(memory_span)
            trace.add_attribute("memory_read_latency_ms", round(elapsed_ms() - memory_started, 2))
            trace.add_attribute("memory_backend", memory_context.backend_name)
            trace.add_attribute("memory_turn_count", len(memory_context.recent_turns))
            trace.add_attribute("memory_has_summary", bool(memory_context.summary))
            trace.add_attribute("memory_key_fact_keys", sorted(memory_context.key_facts.keys()))

            rewrite_span = trace.start_span("query.rewrite")
            rewrite_result = self.query_rewriter.rewrite(
                request.message,
                recent_turns=memory_context.recent_turns,
                key_facts=memory_context.key_facts,
            )
            trace.end_span(rewrite_span)
            rewritten_query = rewrite_result.rewritten_query
            trace.add_attribute("rewritten_query", rewritten_query)
            trace.add_attribute("query_rewrite_changed", rewrite_result.changed)
            trace.add_attribute("query_rewrite_reason", rewrite_result.reason)

            intent_span = trace.start_span("intent.classify")
            intent_result = self.intent_classifier.classify(rewritten_query) # 意图识别
            trace.end_span(intent_span)
            intent = intent_result.intent
            slots = intent_result.slots
            confidence = intent_result.confidence
            intent_reason = intent_result.reason
            trace.add_attribute("intent", intent)
            trace.add_attribute("slots", slots)
            trace.add_attribute("confidence", confidence)
            trace.add_attribute("intent_reason", intent_reason)

            auth_span = trace.start_span("auth.build_context")
            auth_context = self.permission_checker.build_context(request, slots)
            trace.end_span(auth_span)
            for key, value in auth_context.to_trace_attributes().items():
                trace.add_attribute(key, value)

            if confidence < settings.intent_low_confidence_threshold:
                output_span = trace.start_span("safety.output")
                output_safety = self.safety_guard.scan_output(LOW_CONFIDENCE_ANSWER, trace_id=trace.trace_id)
                trace.end_span(output_span)
                trace.add_attribute("fallback", "low_confidence")
                trace.add_attribute("output_safety", output_safety.to_dict())
                log_event("chat.low_confidence", trace.to_log_payload())
                await self._publish_safety_review_if_needed(request, trace.trace_id, output_safety)
                response = ChatResponse(
                    answer=LOW_CONFIDENCE_ANSWER,
                    intent=intent,
                    slots=slots,
                    confidence=confidence,
                    intent_reason=intent_reason,
                    sources=[],
                    tool_calls=[],
                    trace_id=trace.trace_id,
                    latency_ms=trace.latency_ms,
                    rewritten_query=rewritten_query,
                    safety_result=_safety_payload(input_safety, output_safety),
                )
                await self._publish_chat_finished(request, response, input_safety, output_safety)
                return response

            # 路由
            route_span = trace.start_span("router.route", {"intent": intent})
            route_result = await self.router.route(
                intent_result,
                rewritten_query,
                auth_context.effective_user_id,
                recent_turns=memory_context.recent_turns,
                memory_summary=memory_context.summary,
                key_facts=memory_context.key_facts,
                rewritten_query=rewritten_query,
                auth_context=auth_context,
                trace_id=trace.trace_id,
            )
            trace.end_span(route_span)
            output_span = trace.start_span("safety.output")
            output_safety = self.safety_guard.scan_output(route_result.answer, trace_id=trace.trace_id)
            trace.end_span(output_span)
            trace.add_attribute("output_safety", output_safety.to_dict())
            await self._publish_route_events(request, trace.trace_id, route_result)
            await self._publish_audit_events(request, trace.trace_id)
            await self._publish_safety_review_if_needed(request, trace.trace_id, output_safety)
            if output_safety.action != SafetyAction.ALLOW:
                error = "SAFETY_OUTPUT_BLOCKED" if output_safety.action == SafetyAction.BLOCK else "SAFETY_REVIEW_REQUIRED"
                trace.add_attribute("error", error)
                log_event("chat.output_safety_blocked", trace.to_log_payload())
                response = ChatResponse(
                    answer=OUTPUT_BLOCKED_ANSWER,
                    intent=intent,
                    slots=slots,
                    confidence=confidence,
                    intent_reason=intent_reason,
                    sources=[],
                    tool_calls=[],
                    trace_id=trace.trace_id,
                    latency_ms=trace.latency_ms,
                    error=error,
                    rewritten_query=route_result.rewritten_query or rewritten_query,
                    safety_result=_safety_payload(input_safety, output_safety),
                )
                await self._publish_chat_finished(request, response, input_safety, output_safety)
                return response

            memory_write_span = trace.start_span("memory.save")
            memory_write_started = elapsed_ms()
            await self.memory.save_turn(
                request.user_id,
                request.session_id,
                request.message,
                route_result.answer,
                slots,
                route_result.tool_calls,
            )
            trace.end_span(memory_write_span)
            trace.add_attribute("memory_write_latency_ms", round(elapsed_ms() - memory_write_started, 2))
            trace.add_attribute("memory_backend_after_write", self.memory.store.backend_name)

            trace.add_attribute("tool_calls", [call.model_dump() for call in route_result.tool_calls])
            trace.add_attribute("retrieved_sources", [source.model_dump() for source in route_result.sources])
            trace.add_attribute("rbac_allowed", True)
            log_event("chat.completed", trace.to_log_payload())

            response = ChatResponse(
                answer=route_result.answer,
                intent=intent,
                slots=slots,
                confidence=confidence,
                intent_reason=intent_reason,
                sources=route_result.sources,
                tool_calls=route_result.tool_calls,
                trace_id=trace.trace_id,
                latency_ms=trace.latency_ms,
                rewritten_query=route_result.rewritten_query or rewritten_query,
                safety_result=_safety_payload(input_safety, output_safety),
            )
            await self._publish_chat_finished(request, response, input_safety, output_safety)
            return response
        except SafetyViolation as exc:
            trace.end_span(error=str(exc))
            trace.add_attribute("error", str(exc))
            if exc.result is not None:
                safety_key = "tool_param_safety" if exc.result.scope == "tool" else f"{exc.result.scope}_safety"
                trace.add_attribute(safety_key, exc.result.to_dict())
            log_event("chat.safety_blocked", trace.to_log_payload())
            await self._publish_safety_review_if_needed(request, trace.trace_id, exc.result)
            await self._publish_audit_events(request, trace.trace_id)
            response = ChatResponse(
                answer=str(exc),
                intent=intent,
                slots=slots,
                confidence=confidence,
                intent_reason=intent_reason,
                sources=[],
                tool_calls=[],
                trace_id=trace.trace_id,
                latency_ms=trace.latency_ms,
                error="SAFETY_BLOCKED",
                rewritten_query=rewritten_query,
                safety_result=_safety_payload(input_safety, output_safety, exc.result),
            )
            await self._publish_chat_finished(request, response, input_safety, output_safety, exc.result)
            return response
        except ForbiddenError as exc:
            trace.end_span(error=str(exc))
            trace.add_attribute("error", str(exc))
            trace.add_attribute("rbac_allowed", False)
            log_event("chat.blocked", trace.to_log_payload())
            await self._publish_audit_events(request, trace.trace_id)
            response = ChatResponse(
                answer=str(exc),
                intent=intent,
                slots=slots,
                confidence=confidence,
                intent_reason=intent_reason,
                sources=[],
                tool_calls=[],
                trace_id=trace.trace_id,
                latency_ms=trace.latency_ms,
                error=str(exc),
                rewritten_query=rewritten_query,
                safety_result=_safety_payload(input_safety, output_safety),
            )
            await self._publish_chat_finished(request, response, input_safety, output_safety)
            return response
        except Exception as exc:
            trace.end_span(error=str(exc))
            trace.add_attribute("error", str(exc))
            log_event("chat.failed", trace.to_log_payload(), level="error")
            await self._publish_audit_events(request, trace.trace_id)
            response = ChatResponse(
                answer="服务处理失败，请稍后再试或转人工客服。",
                intent=intent,
                slots=slots,
                confidence=confidence,
                intent_reason=intent_reason,
                sources=[],
                tool_calls=[],
                trace_id=trace.trace_id,
                latency_ms=trace.latency_ms,
                error=str(exc),
                rewritten_query=rewritten_query,
                safety_result=_safety_payload(input_safety, output_safety),
            )
            await self._publish_chat_finished(request, response, input_safety, output_safety)
            return response
        finally:
            trace.add_attribute("latency_ms", trace.latency_ms)
            trace.finish(error=str(trace.attributes.get("error") or "") or None)
            self.trace_repository.save(trace)
            reset_current_trace(trace_token)

    async def _publish_route_events(self, request: ChatRequest, trace_id: str, route_result: RouteResult) -> None:
        """发布工具调用产生的业务事件。

        Router 继续只负责 intent 分发和工具调用，事件发送统一收口在主编排层，避免
        tools 或 router 直接依赖 RocketMQ。
        """

        for call in route_result.tool_calls:
            if call.tool_name == "create_ticket" and call.success:
                published = await self.event_bus.publish_ticket_created(
                    trace_id=trace_id,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    payload={
                        "ticket_id": call.output.get("ticket_id"),
                        "status": call.output.get("status"),
                        "issue_type": call.output.get("issue_type") or call.input.get("issue_type"),
                        "tool_latency_ms": call.latency_ms,
                    },
                )
                self._record_event_publish(EventType.TICKET_CREATED.value, published)

    async def _publish_audit_events(self, request: ChatRequest, trace_id: str) -> None:
        audit_logger = getattr(self.router, "audit_logger", None)
        if audit_logger is None or not hasattr(audit_logger, "drain_records"):
            return
        for record in audit_logger.drain_records(trace_id):
            published = await self.event_bus.publish_audit_log_created(
                trace_id=trace_id,
                user_id=request.user_id,
                session_id=request.session_id,
                payload={
                    "action": record.get("action"),
                    "permission": record.get("permission"),
                    "intent": record.get("intent"),
                    "tool_name": record.get("tool_name"),
                    "resource_type": record.get("resource_type"),
                    "allowed": record.get("allowed"),
                    "success": record.get("success"),
                    "reason": record.get("reason"),
                    "role": record.get("role"),
                    "actor_user_id_masked": record.get("actor_user_id_masked"),
                    "target_user_id_masked": record.get("target_user_id_masked"),
                    "metadata": record.get("metadata") or {},
                },
            )
            self._record_event_publish(EventType.AUDIT_LOG_CREATED.value, published)

    async def _publish_safety_review_if_needed(
        self,
        request: ChatRequest,
        trace_id: str,
        result: SafetyResult | None,
    ) -> None:
        if result is None or not result.review_queued:
            return
        published = await self.event_bus.publish_safety_review_required(
            trace_id=trace_id,
            user_id=request.user_id,
            session_id=request.session_id,
            payload={
                "scope": result.scope,
                "risk_level": result.risk_level.value,
                "action": result.action.value,
                "risk_types": sorted({finding.risk_type for finding in result.findings}),
                "finding_count": len(result.findings),
            },
        )
        self._record_event_publish(EventType.SAFETY_REVIEW_REQUIRED.value, published)

    async def _publish_chat_finished(
        self,
        request: ChatRequest,
        response: ChatResponse,
        *safety_results: SafetyResult | None,
    ) -> None:
        published = await self.event_bus.publish_ai_qa_finished(
            trace_id=response.trace_id,
            user_id=request.user_id,
            session_id=request.session_id,
            payload={
                "intent": response.intent,
                "latency_ms": response.latency_ms,
                "tool_count": len(response.tool_calls),
                "source_count": len(response.sources),
                "safety_risk_level": _max_safety_risk_level(*safety_results),
                "error": response.error,
                "confidence": response.confidence,
            },
        )
        self._record_event_publish(EventType.AI_QA_FINISHED.value, published)

    def _record_event_publish(self, event_type: str, published: bool) -> None:
        trace = get_current_trace()
        if trace is None:
            return
        result = {
            "event_type": event_type,
            "publish_success": published,
            "producer_type": type(self.event_bus.producer).__name__,
        }
        existing = list(trace.attributes.get("event_publish_result") or [])
        existing.append(result)
        trace.add_attribute("event_publish_result", existing)
        add_event("event.publish", result)


def _safety_payload(*results: SafetyResult | None) -> dict[str, object] | None:
    payload: dict[str, object] = {}
    for result in results:
        if result is None:
            continue
        key = "tool_param_safety" if result.scope == "tool" else f"{result.scope}_safety"
        payload[key] = result.to_dict()
    return payload or None


def _max_safety_risk_level(*results: SafetyResult | None) -> str:
    order = {"SAFE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    level = "SAFE"
    for result in results:
        if result is None:
            continue
        value = result.risk_level.value
        if order[value] > order[level]:
            level = value
    return level
