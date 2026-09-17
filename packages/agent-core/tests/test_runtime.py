import asyncio

from agent_core import Tool, ToolRegistry, aexecute_tool_calls, execute_tool_calls


def test_execute_tool_calls_returns_call_and_result_events():
    registry = ToolRegistry([Tool("echo", "", {}, lambda text: text)])

    events = list(
        execute_tool_calls(
            registry,
            [{"id": "c1", "name": "echo", "arguments": {"text": "ok"}}],
        )
    )

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[-1].result == "ok"


def test_execute_tool_calls_normalizes_non_dict_arguments():
    registry = ToolRegistry([Tool("echo", "", {}, lambda: "ok")])

    events = list(
        execute_tool_calls(
            registry,
            [{"id": "c1", "name": "echo", "arguments": "not-an-object"}],
        )
    )

    assert events[0].arguments == {}
    assert events[-1].result == "ok"


def test_async_execute_tool_calls_awaits_async_handler():
    async def async_echo(text):
        await asyncio.sleep(0)
        return text

    async def collect():
        registry = ToolRegistry([Tool("echo", "", {}, async_echo)])
        return [
            event
            async for event in aexecute_tool_calls(
                registry,
                [{"id": "c1", "name": "echo", "arguments": {"text": "ok"}}],
            )
        ]

    events = asyncio.run(collect())

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[-1].result == "ok"
