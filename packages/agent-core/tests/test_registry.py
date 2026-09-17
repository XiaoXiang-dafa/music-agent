import asyncio

from agent_core import Tool, ToolCallEvent, ToolRegistry, ToolResultEvent


def test_registry_emits_openai_schema_and_runs_tool():
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="Echo text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=lambda text: text,
        )
    )

    assert registry.openai_defs()[0]["function"]["name"] == "echo"
    assert registry.run("echo", {"text": "ok"}) == "ok"


def test_registry_returns_json_safe_error_for_unknown_tool():
    result = ToolRegistry().run("missing", {})

    assert result == {
        "error": "unknown_tool",
        "message": "Unknown tool: missing",
        "tool": "missing",
        "available": [],
    }


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry([Tool("echo", "", {}, lambda: "first")])

    try:
        registry.register(Tool("echo", "", {}, lambda: "second"))
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate tool registration should fail")


def test_registry_wraps_invalid_arguments_and_handler_errors():
    registry = ToolRegistry(
        [
            Tool("needs_text", "", {}, lambda text: text),
            Tool("explode", "", {}, lambda: 1 / 0),
        ]
    )

    invalid = registry.run("needs_text", {})
    failed = registry.run("explode", {})

    assert invalid["error"] == "invalid_arguments"
    assert invalid["tool"] == "needs_text"
    assert failed["error"] == "tool_execution_error"
    assert failed["tool"] == "explode"


def test_arun_awaits_async_handler_and_supports_sync_handler():
    async def async_echo(text):
        await asyncio.sleep(0)
        return text

    registry = ToolRegistry(
        [
            Tool("async_echo", "", {}, async_echo),
            Tool("sync_echo", "", {}, lambda text: text),
        ]
    )

    assert asyncio.run(registry.arun("async_echo", {"text": "async"})) == "async"
    assert asyncio.run(registry.arun("sync_echo", {"text": "sync"})) == "sync"


def test_events_have_stable_json_safe_shape():
    call = ToolCallEvent(name="echo", arguments={"text": "ok"}, call_id="call_1")
    result = ToolResultEvent(name="echo", result={"value": object()}, call_id="call_1")

    assert call.to_dict() == {
        "type": "tool_call",
        "name": "echo",
        "arguments": {"text": "ok"},
        "id": "call_1",
    }
    assert result.to_dict()["type"] == "tool_result"
    assert isinstance(result.to_dict()["result"]["value"], str)
