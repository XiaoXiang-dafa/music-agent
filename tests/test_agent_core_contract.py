from types import SimpleNamespace
from time import sleep

from agent import AgentConfig
from agent import loop as agent_loop
from agent.registry import ToolRegistry
from agent_core import ToolCallEvent, ToolRegistry as CoreToolRegistry, ToolResultEvent
from tools import AgentContext, build_registry


def test_registry_contract_before_migration():
    registry = ToolRegistry()
    registry.register(
        "echo",
        {"type": "function", "function": {"parameters": {}}},
        lambda text="": text,
    )

    assert registry.call("echo", {"text": "ok"}) == "ok"
    assert registry.call("missing", {})["error"]


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    schema = {"type": "function", "function": {"parameters": {}}}
    registry.register("echo", schema, lambda: "first")

    try:
        registry.register("echo", schema, lambda: "second")
    except ValueError as exc:
        assert "已存在" in str(exc)
    else:
        raise AssertionError("duplicate tool registration should fail")


def test_wechat_registry_delegates_to_agent_core():
    registry = ToolRegistry()

    assert isinstance(registry.core, CoreToolRegistry)


def test_wechat_loop_uses_shared_executor(monkeypatch):
    used = False

    def fake_executor(core, calls):
        nonlocal used
        used = True
        call = calls[0]
        yield ToolCallEvent("echo", call["arguments"], call["id"])
        yield ToolResultEvent("echo", "ok", call["id"])

    tool_delta = SimpleNamespace(
        index=0,
        id="call_1",
        function=SimpleNamespace(name="echo", arguments='{"text":"ok"}'),
    )
    streams = iter(
        [
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="tool_calls",
                            delta=SimpleNamespace(content=None, tool_calls=[tool_delta]),
                        )
                    ]
                )
            ],
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="stop",
                            delta=SimpleNamespace(content="done", tool_calls=None),
                        )
                    ]
                )
            ],
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: iter(next(streams)))
        )
    )
    registry = ToolRegistry()
    registry.register(
        "echo",
        {"type": "function", "function": {"parameters": {}}},
        lambda text="": text,
    )
    monkeypatch.setattr(agent_loop, "execute_tool_calls", fake_executor)

    events = list(
        agent_loop.stream_agent(
            client,
            registry,
            "system",
            [{"role": "user", "content": "echo ok"}],
            AgentConfig("mock-model"),
        )
    )

    assert used
    assert [event["type"] for event in events] == [
        "tool_call",
        "tool_result",
        "reply_chunk",
        "done",
    ]
    assert events[0]["call_id"] == "call_1"
    assert events[1]["call_id"] == "call_1"
    assert events[1]["status"] == "success"
    assert isinstance(events[1]["duration_ms"], int)
    assert events[1]["duration_ms"] >= 0


def test_run_agent_returns_tool_results_with_error_metadata(monkeypatch):
    def fake_executor(core, calls):
        call = calls[0]
        yield ToolCallEvent("echo", call["arguments"], call["id"])
        yield ToolResultEvent("echo", {"error": "boom"}, call["id"])

    tool_delta = SimpleNamespace(
        index=0,
        id="call_error",
        function=SimpleNamespace(name="echo", arguments='{"text":"bad"}'),
    )
    streams = iter(
        [
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="tool_calls",
                            delta=SimpleNamespace(content=None, tool_calls=[tool_delta]),
                        )
                    ]
                )
            ],
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="stop",
                            delta=SimpleNamespace(content="done", tool_calls=None),
                        )
                    ]
                )
            ],
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: iter(next(streams)))
        )
    )
    registry = ToolRegistry()
    registry.register(
        "echo",
        {"type": "function", "function": {"parameters": {}}},
        lambda text="": text,
    )
    monkeypatch.setattr(agent_loop, "execute_tool_calls", fake_executor)

    result = agent_loop.run_agent(
        client,
        registry,
        "system",
        [{"role": "user", "content": "echo bad"}],
        AgentConfig("mock-model"),
    )

    assert result["tool_calls"] == [
        {"name": "echo", "args": {"text": "bad"}}
    ]
    assert len(result["tool_results"]) == 1
    tool_result = result["tool_results"][0]
    assert tool_result["name"] == "echo"
    assert tool_result["result"] == {"error": "boom"}
    assert tool_result["call_id"] == "call_error"
    assert tool_result["status"] == "error"
    assert isinstance(tool_result["duration_ms"], int)
    assert tool_result["duration_ms"] >= 0


def test_stream_agent_duration_covers_real_tool_execution():
    tool_delta = SimpleNamespace(
        index=0,
        id="call_slow",
        function=SimpleNamespace(name="slow_echo", arguments='{"text":"ok"}'),
    )
    streams = iter(
        [
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="tool_calls",
                            delta=SimpleNamespace(content=None, tool_calls=[tool_delta]),
                        )
                    ]
                )
            ],
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="stop",
                            delta=SimpleNamespace(content="done", tool_calls=None),
                        )
                    ]
                )
            ],
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: iter(next(streams)))
        )
    )
    registry = ToolRegistry()

    def slow_echo(text=""):
        sleep(0.025)
        return text

    registry.register(
        "slow_echo",
        {"type": "function", "function": {"parameters": {}}},
        slow_echo,
    )

    events = list(
        agent_loop.stream_agent(
            client,
            registry,
            "system",
            [{"role": "user", "content": "echo slowly"}],
            AgentConfig("mock-model"),
        )
    )

    tool_result = next(event for event in events if event["type"] == "tool_result")
    assert tool_result["result"] == "ok"
    assert tool_result["duration_ms"] >= 15


def test_music_agent_registers_nine_domain_tools():
    context = AgentContext(
        client=None,
        model="mock-model",
        memory=None,
        session_id="test-session",
    )

    registry = build_registry(context)

    assert set(registry.names()) == {
        "search_songs",
        "get_song_url",
        "get_lyrics",
        "get_daily_recommendation",
        "get_weather",
        "play_song",
        "save_favorite",
        "remember_taste",
        "get_user_profile",
    }
    assert len(registry.get_schemas()) == 9
