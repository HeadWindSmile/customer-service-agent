import asyncio
import json

from app.events.event_schema import Event
from app.events.event_type import EventType
from app.events.mock_producer import MockEventProducer


def test_mock_event_producer_appends_jsonl_records(tmp_path):
    async def scenario():
        event_path = tmp_path / "events.jsonl"
        producer = MockEventProducer(log_path=str(event_path))

        await producer.send(
            Event(
                event_type=EventType.TICKET_CREATED,
                trace_id="trace-ticket",
                user_id="u1001",
                session_id="session-ticket",
                payload={"ticket_id": "TCK-001"},
            )
        )
        await producer.send(
            Event(
                event_type=EventType.AI_QA_FINISHED,
                trace_id="trace-chat",
                user_id="u1001",
                session_id="session-chat",
                payload={"intent": "ticket_create"},
            )
        )

        records = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
        assert [record["event_type"] for record in records] == ["TICKET_CREATED", "AI_QA_FINISHED"]
        assert records[0]["payload"]["ticket_id"] == "TCK-001"
        assert records[1]["payload"]["intent"] == "ticket_create"

    asyncio.run(scenario())
