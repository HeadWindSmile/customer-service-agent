from app.agents.intent_classifier import IntentClassifier
from app.agents.prompts import LOW_CONFIDENCE_ANSWER
from app.agents.router import CustomerRouter
from app.auth.permission import PermissionChecker, PermissionDenied
from app.config import settings
from app.memory.memory_store import InMemoryConversationMemory
from app.observability.logger import log_event
from app.observability.tracing import TraceContext
from app.safety.guard import SafetyGuard, SafetyViolation
from app.schemas.chat import ChatRequest, ChatResponse


class CustomerAgent:
    """主编排层串起权限、安全、意图、路由、记忆和观测，方便面试时讲清主链路。"""

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.router = CustomerRouter()
        self.memory = InMemoryConversationMemory()
        self.safety_guard = SafetyGuard()
        self.permission_checker = PermissionChecker()

    async def handle(self, request: ChatRequest) -> ChatResponse:
        trace = TraceContext.new()
        intent = "unknown"
        slots: dict[str, object] = {}
        confidence = 0.0
        intent_reason = ""
        try:
            self.safety_guard.check_input(request.message)  # 检查用户输入有没有敏感词
            intent_result = self.intent_classifier.classify(request.message) # 意图识别
            intent = intent_result.intent
            slots = intent_result.slots
            confidence = intent_result.confidence
            intent_reason = intent_result.reason

            # 权限检查
            target_user_id = self.permission_checker.resolve_target_user_id(request, slots)
            audit_event = self.permission_checker.check(request, target_user_id)
            if audit_event:
                log_event("audit.agent_access", audit_event)

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
                )

            # 读取会话记忆
            recent_turns = self.memory.get_recent(request.session_id)
            trace.add_attribute("memory_turn_count", len(recent_turns))

            # 路由
            route_result = await self.router.route(
                intent_result,
                request.message,
                target_user_id,
                recent_turns=recent_turns,
            )
            self.safety_guard.check_output(route_result.answer)
            self.memory.add_turn(request.session_id, request.message, route_result.answer)

            trace.add_attribute("intent", intent)
            trace.add_attribute("slots", slots)
            trace.add_attribute("confidence", confidence)
            trace.add_attribute("intent_reason", intent_reason)
            trace.add_attribute("tool_calls", [call.model_dump() for call in route_result.tool_calls])
            trace.add_attribute("retrieved_sources", [source.model_dump() for source in route_result.sources])
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
            )
        except (SafetyViolation, PermissionDenied) as exc:
            trace.add_attribute("error", str(exc))
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
            )
