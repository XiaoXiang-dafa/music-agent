import sqlite3

from observability import TraceRecorder


def test_trace_persists_run_and_sanitized_tool_event(tmp_path):
    db_path = tmp_path / "traces.db"
    recorder = TraceRecorder(db_path)
    trace_id = recorder.start_run("session-a", "demo")

    recorder.record_tool(
        trace_id,
        1,
        "call-1",
        "play_song",
        "success",
        7,
        {
            "source": "netease",
            "fallback_used": True,
            "attempted_sources": ["qq", "netease"],
            "url": "data:secret",
            "lyrics": "private text",
        },
    )
    recorder.finish_run(trace_id, "success", 2, 1, 12)

    reopened = TraceRecorder(db_path)
    detail = reopened.get_run(trace_id)

    assert detail["run"]["status"] == "success"
    assert "session_id" not in detail["run"]
    assert detail["events"] == [
        {
            "sequence": 1,
            "call_id": "call-1",
            "tool_name": "play_song",
            "status": "success",
            "duration_ms": 7,
            "source": "netease",
            "fallback_used": True,
            "attempted_sources": ["qq", "netease"],
            "error_type": None,
        }
    ]
    assert "url" not in detail["events"][0]
    assert "lyrics" not in detail["events"][0]
    with sqlite3.connect(db_path) as connection:
        stored = " ".join(
            str(value)
            for row in connection.execute("SELECT * FROM tool_events")
            for value in row
            if value is not None
        )
    assert "data:secret" not in stored
    assert "private text" not in stored


def test_trace_records_safe_error_type_and_window_stats(tmp_path):
    recorder = TraceRecorder(tmp_path / "traces.db")
    failed_id = recorder.start_run("session-a", "live")
    recorder.record_tool(
        failed_id,
        1,
        "call-err",
        "play_song",
        "error",
        -4,
        {
            "error_type": "TimeoutError",
            "error": "secret stack trace",
            "url": "https://private.example/audio.mp3",
        },
    )
    recorder.finish_run(
        failed_id, "error", 1, 1, -2, error_type="RuntimeError"
    )

    success_id = recorder.start_run("session-b", "demo")
    recorder.finish_run(success_id, "success", 1, 0, 10)

    payload = recorder.list_runs(limit=10)
    assert payload["stats"] == {
        "run_count": 2,
        "success_count": 1,
        "success_rate": 0.5,
        "average_duration_ms": 5.0,
        "tool_call_count": 1,
        "fallback_count": 0,
    }
    assert payload["runs"][0]["trace_id"] == success_id
    assert "session_id" not in payload["runs"][0]
    error_detail = recorder.get_run(failed_id)
    assert error_detail["run"]["error_type"] == "RuntimeError"
    assert error_detail["events"][0]["status"] == "error"
    assert error_detail["events"][0]["duration_ms"] == 0
    assert error_detail["events"][0]["error_type"] == "TimeoutError"
    assert "error" not in error_detail["events"][0]
    assert "url" not in error_detail["events"][0]


def test_trace_limit_and_missing_trace(tmp_path):
    recorder = TraceRecorder(tmp_path / "traces.db")
    first = recorder.start_run("session-a", "demo")
    recorder.finish_run(first, "success", 1, 0, 1)
    second = recorder.start_run("session-a", "demo")
    recorder.finish_run(second, "success", 1, 0, 2)

    assert len(recorder.list_runs(limit=1)["runs"]) == 1
    assert recorder.get_run("does-not-exist") is None


def test_trace_window_stats_and_limit_bounds(tmp_path):
    recorder = TraceRecorder(tmp_path / "traces.db")
    for index in range(105):
        trace_id = recorder.start_run(f"session-{index}", "demo")
        recorder.record_tool(
            trace_id,
            1,
            f"call-{index}",
            "play_song",
            "success",
            index,
            {"fallback_used": index == 104},
        )
        recorder.finish_run(trace_id, "success", 1, 1, index)

    assert recorder.list_runs(limit=0)["stats"]["run_count"] == 1
    assert recorder.list_runs(limit=-5)["stats"]["run_count"] == 1
    bounded = recorder.list_runs(limit=1000)
    assert bounded["stats"]["run_count"] == 100
    assert bounded["stats"]["tool_call_count"] == 100
    assert bounded["stats"]["fallback_count"] == 1


def test_empty_trace_stats_are_zero(tmp_path):
    payload = TraceRecorder(tmp_path / "traces.db").list_runs()
    assert payload["runs"] == []
    assert payload["stats"] == {
        "run_count": 0,
        "success_count": 0,
        "success_rate": 0,
        "average_duration_ms": 0,
        "tool_call_count": 0,
        "fallback_count": 0,
    }
