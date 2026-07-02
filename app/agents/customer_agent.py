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
from app.safety.guard import SafetyGuard, SafetyViolation
from app.schemas.chat import ChatRequest, ChatResponse
from app.utils.time import elapsed_ms


class CustomerAgent:
    """主编排层串起权限、安全、意图、路由、记忆和观测，方便面试时讲清主链路。"""

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.router = CustomerRouter()
        self.memory = ConversationMemoryManager(create_memory_store())
        self.query_rewriter = QueryRewriter()
        self.safety_guard = SafetyGuard()
        self.permission_checker = PermissionChecker()

    async def handle(self, request: ChatRequest) -> ChatResponse:
        trace = TraceContext.new()
        intent = "unknown"
        slots: dict[str, object] = {}
        confidence = 0.0
        intent_reason = ""
        rewritten_query: str | None = None
        try:
            self.safety_guard.check_input(request.message)  # 检查用户输入有没有敏感词

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
                trace.add_attribute("intent", intent)
                trace.add_attribute("slots", slots)
                trace.add_attribute("confidence", confidence)
                trace.add_attribute("intent_reason", intent_reason)
                trace.add_attribute("fallback", "low_confidence")
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
            self.safety_guard.check_output(route_result.answer)

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
            )
        except (SafetyViolation, ForbiddenError) as exc:
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
            )
