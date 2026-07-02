from app.agents.intent_classifier import IntentClassifier
from app.agents.prompts import LOW_CONFIDENCE_ANSWER
from app.agents.query_rewriter import QueryRewriter
from app.agents.router import CustomerRouter
from app.auth.rbac import ForbiddenError, PermissionChecker
from app.config import settings
from app.memory.factory import create_memory_store
from app.memory.manager import ConversationMemoryManager
from app.observability.logger import log_event
from app.observability.tracing import TraceContext
from app.safety.guard import INPUT_BLOCKED_ANSWER, INPUT_REVIEW_ANSWER, OUTPUT_BLOCKED_ANSWER, SafetyGuard, SafetyViolation
from app.safety.risk_level import SafetyAction, SafetyResult
from app.schemas.chat import ChatRequest, ChatResponse
from app.utils.time import elapsed_ms


class CustomerAgent:
    """主编排层串起权限、安全、意图、路由、记忆和观测，方便面试时讲清主链路。"""

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.memory = ConversationMemoryManager(create_memory_store())
        self.query_rewriter = QueryRewriter()
        self.safety_guard = SafetyGuard()
        self.router = CustomerRouter(safety_guard=self.safety_guard)
        self.permission_checker = PermissionChecker()

    async def handle(self, request: ChatRequest) -> ChatResponse:
        trace = TraceContext.new()
        intent = "unknown"
        slots: dict[str, object] = {}
        confidence = 0.0
        intent_reason = ""
        rewritten_query: str | None = None
        input_safety: SafetyResult | None = None
        output_safety: SafetyResult | None = None
        try:
            input_safety = self.safety_guard.scan_input(request.message, trace_id=trace.trace_id)
            trace.add_attribute("input_safety", input_safety.to_dict())
            if input_safety.action != SafetyAction.ALLOW:
                answer = INPUT_BLOCKED_ANSWER if input_safety.action == SafetyAction.BLOCK else INPUT_REVIEW_ANSWER
                error = "SAFETY_INPUT_BLOCKED" if input_safety.action == SafetyAction.BLOCK else "SAFETY_REVIEW_REQUIRED"
                trace.add_attribute("error", error)
                log_event("chat.safety_blocked", trace.to_log_payload())
                return ChatResponse(
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

            memory_started = elapsed_ms()
            memory_context = await self.memory.load_context(request.user_id, request.session_id)
            trace.add_attribute("memory_read_latency_ms", round(elapsed_ms() - memory_started, 2))
            trace.add_attribute("memory_backend", memory_context.backend_name)
            trace.add_attribute("memory_turn_count", len(memory_context.recent_turns))
            trace.add_attribute("memory_has_summary", bool(memory_context.summary))
            trace.add_attribute("memory_key_fact_keys", sorted(memory_context.key_facts.keys()))

            rewrite_result = self.query_rewriter.rewrite(
                request.message,
                recent_turns=memory_context.recent_turns,
                key_facts=memory_context.key_facts,
            )
            rewritten_query = rewrite_result.rewritten_query
            trace.add_attribute("rewritten_query", rewritten_query)
            trace.add_attribute("query_rewrite_changed", rewrite_result.changed)
            trace.add_attribute("query_rewrite_reason", rewrite_result.reason)

            intent_result = self.intent_classifier.classify(rewritten_query) # 意图识别
            intent = intent_result.intent
            slots = intent_result.slots
            confidence = intent_result.confidence
            intent_reason = intent_result.reason

            auth_context = self.permission_checker.build_context(request, slots)
            for key, value in auth_context.to_trace_attributes().items():
                trace.add_attribute(key, value)

            if confidence < settings.intent_low_confidence_threshold:
                output_safety = self.safety_guard.scan_output(LOW_CONFIDENCE_ANSWER, trace_id=trace.trace_id)
                trace.add_attribute("intent", intent)
                trace.add_attribute("slots", slots)
                trace.add_attribute("confidence", confidence)
                trace.add_attribute("intent_reason", intent_reason)
                trace.add_attribute("fallback", "low_confidence")
                trace.add_attribute("output_safety", output_safety.to_dict())
                log_event("chat.low_confidence", trace.to_log_payload())
                return ChatResponse(
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

            # 路由
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
            output_safety = self.safety_guard.scan_output(route_result.answer, trace_id=trace.trace_id)
            trace.add_attribute("output_safety", output_safety.to_dict())
            if output_safety.action != SafetyAction.ALLOW:
                error = "SAFETY_OUTPUT_BLOCKED" if output_safety.action == SafetyAction.BLOCK else "SAFETY_REVIEW_REQUIRED"
                trace.add_attribute("error", error)
                log_event("chat.output_safety_blocked", trace.to_log_payload())
                return ChatResponse(
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

            memory_write_started = elapsed_ms()
            await self.memory.save_turn(
                request.user_id,
                request.session_id,
                request.message,
                route_result.answer,
                slots,
                route_result.tool_calls,
            )
            trace.add_attribute("memory_write_latency_ms", round(elapsed_ms() - memory_write_started, 2))
            trace.add_attribute("memory_backend_after_write", self.memory.store.backend_name)

            trace.add_attribute("intent", intent)
            trace.add_attribute("slots", slots)
            trace.add_attribute("confidence", confidence)
            trace.add_attribute("intent_reason", intent_reason)
            trace.add_attribute("tool_calls", [call.model_dump() for call in route_result.tool_calls])
            trace.add_attribute("retrieved_sources", [source.model_dump() for source in route_result.sources])
            trace.add_attribute("rbac_allowed", True)
            log_event("chat.completed", trace.to_log_payload())

            return ChatResponse(
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
        except SafetyViolation as exc:
            trace.add_attribute("error", str(exc))
            if exc.result is not None:
                safety_key = "tool_param_safety" if exc.result.scope == "tool" else f"{exc.result.scope}_safety"
                trace.add_attribute(safety_key, exc.result.to_dict())
            log_event("chat.safety_blocked", trace.to_log_payload())
            return ChatResponse(
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
        except ForbiddenError as exc:
            trace.add_attribute("error", str(exc))
            trace.add_attribute("rbac_allowed", False)
            log_event("chat.blocked", trace.to_log_payload())
            return ChatResponse(
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
        except Exception as exc:
            trace.add_attribute("error", str(exc))
            log_event("chat.failed", trace.to_log_payload(), level="error")
            return ChatResponse(
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


def _safety_payload(*results: SafetyResult | None) -> dict[str, object] | None:
    payload: dict[str, object] = {}
    for result in results:
        if result is None:
            continue
        key = "tool_param_safety" if result.scope == "tool" else f"{result.scope}_safety"
        payload[key] = result.to_dict()
    return payload or None
