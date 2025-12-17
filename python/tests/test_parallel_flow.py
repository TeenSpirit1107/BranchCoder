import tempfile

import pytest


TASK_DESCRIPTIONS = ["Task Alpha", "Task Beta"]


class DummyChatClient:
    def __init__(self):
        self.call_count = 0

    async def ask(self, messages, tools=None, **kwargs):
        self.call_count += 1
        last_user = next(
            msg for msg in reversed(messages) if msg.get("role") == "user"
        )
        content = last_user.get("content", "")

        if "parallel" in content:
            if self.call_count == 1:
                return {
                    "type": "tool_call",
                    "tool_name": "execute_parallel_tasks",
                    "tool_args": {"tasks": TASK_DESCRIPTIONS},
                }
            return {"type": "answer", "answer": "Parent final message"}

        if content == TASK_DESCRIPTIONS[0]:
            return {"type": "answer", "answer": "Alpha done"}

        if content == TASK_DESCRIPTIONS[1]:
            return {"type": "answer", "answer": "Beta done"}

        return {"type": "answer", "answer": f"Unhandled payload: {content}"}


@pytest.mark.asyncio
async def test_parallel_tool_flow(monkeypatch):
    monkeypatch.setattr("agents.flow.AsyncChatClientWrapper", DummyChatClient)

    from agents.react_flow import ReActFlow
    from models import MessageEvent, ToolResultEvent

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = ReActFlow(tmpdir)
        all_events = []

        async for event in agent.process("Please run parallel tasks", "parent-session"):
            all_events.append(event)

    summary_events = [
        event for event in all_events if isinstance(event, ToolResultEvent)
    ]
    assert summary_events, "Expected at least one tool result event"

    summary_event = summary_events[-1]
    assert "Parallel Execution Results" in summary_event.message
    assert "Task Alpha" in summary_event.message
    assert len(summary_event.result.get("tasks", [])) == len(TASK_DESCRIPTIONS)
    assert summary_event.result["tasks"][0]["result"] == "Alpha done"
    assert summary_event.result["tasks"][1]["result"] == "Beta done"

    final_user_messages = [
        event.message
        for event in all_events
        if isinstance(event, MessageEvent) and event.message
    ]
    assert final_user_messages
    assert final_user_messages[-1] == "Parent final message"

