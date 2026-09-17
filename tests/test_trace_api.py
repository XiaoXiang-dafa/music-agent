import json
import os
import subprocess
from pathlib import Path


def _run_demo_script(tmp_path: Path, script: str) -> dict:
    project_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DEMO_MODE"] = "1"
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("QQMUSIC_COOKIE", None)
    env.pop("WEATHER_API_KEY", None)
    env["PYTHONPATH"] = str(project_dir.parent / "agent-core" / "src")
    completed = subprocess.run(
        ["python3", "-c", script, str(tmp_path / "traces.db")],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_stream_trace_events_and_query_api(tmp_path):
    payload = _run_demo_script(tmp_path, """
import json
import sys
import app
from observability import TraceRecorder
app.trace_recorder = TraceRecorder(sys.argv[1])
client = app.app.test_client()
response = client.post("/api/chat/stream", json={"message": "我想听周杰伦的晴天", "session": "trace-demo"})
events = []
for frame in response.get_data(as_text=True).strip().split("\\n\\n"):
    name = None
    data = None
    for line in frame.splitlines():
        if line.startswith("event:"):
            name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data = json.loads(line.removeprefix("data:").strip())
    if name and data is not None:
        events.append([name, data])
selected = [[name, data] for name, data in events if name in {"start", "tool_call", "tool_result", "done"}]
trace_id = selected[0][1].get("trace_id") if selected else None
listed = client.get("/api/traces?limit=20")
detail = client.get(f"/api/traces/{trace_id}") if trace_id else None
missing = client.get("/api/traces/does-not-exist")
print(json.dumps({"stream_status": response.status_code, "events": selected, "list_status": listed.status_code, "list": listed.get_json(), "detail_status": detail.status_code if detail else None, "detail": detail.get_json() if detail else None, "missing_status": missing.status_code}, ensure_ascii=False))
""")
    assert payload["stream_status"] == 200
    assert [name for name, _ in payload["events"]] == ["start", "tool_call", "tool_result", "done"]
    trace_ids = {data["trace_id"] for _, data in payload["events"]}
    assert len(trace_ids) == 1
    event_map = {name: data for name, data in payload["events"]}
    assert event_map["start"]["mode"] == "demo"
    assert event_map["tool_call"]["call_id"] == event_map["tool_result"]["call_id"]
    assert event_map["tool_result"]["status"] == "success"
    assert event_map["tool_result"]["duration_ms"] >= 0
    assert event_map["done"]["status"] == "success"
    assert event_map["done"]["duration_ms"] >= 0
    assert payload["list_status"] == 200
    assert payload["list"]["stats"]["run_count"] == 1
    assert payload["list"]["stats"]["tool_call_count"] == 1
    assert payload["detail_status"] == 200
    assert payload["detail"]["run"]["status"] == "success"
    assert payload["detail"]["events"][0]["tool_name"] == "play_song"
    serialized = json.dumps(payload["detail"], ensure_ascii=False)
    assert "我想听周杰伦的晴天" not in serialized
    assert "data:audio" not in serialized
    assert payload["missing_status"] == 404


def test_trace_limit_is_bounded_and_invalid_limit_uses_default(tmp_path):
    payload = _run_demo_script(tmp_path, """
import json
import sys
import app
from observability import TraceRecorder
app.trace_recorder = TraceRecorder(sys.argv[1])
client = app.app.test_client()
print(json.dumps({"bounded": client.get("/api/traces?limit=999").status_code, "invalid": client.get("/api/traces?limit=invalid").status_code}))
""")
    assert payload == {"bounded": 200, "invalid": 200}


def test_runtime_prompt_includes_recently_played(tmp_path):
    payload = _run_demo_script(tmp_path, """
import json
import app
memory = app._get_memory("prompt-history")
memory.add_play("晴天", "周杰伦", "demo-qq-1", "qq")
prompt = app._build_system("prompt-history")
print(json.dumps({"has_recent": "最近播放：晴天-周杰伦" in prompt}, ensure_ascii=False))
""")
    assert payload == {"has_recent": True}
