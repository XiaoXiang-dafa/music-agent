import os
import subprocess
from pathlib import Path

from agent import AgentConfig, run_agent
from demo import DemoClient, DemoMusicBackend
from modules import common
from tools import AgentContext, build_registry
from tools.memory import UserMemory


def test_demo_client_runs_playback_through_real_agent_loop(tmp_path):
    client = DemoClient()
    context = AgentContext(
        client=client,
        model="demo-model",
        memory=UserMemory(str(tmp_path / "memory.db"), "demo"),
        session_id="demo",
        extra={"music_backend": DemoMusicBackend()},
    )

    result = run_agent(
        client,
        build_registry(context),
        "你是音乐助手",
        [{"role": "user", "content": "我想听周杰伦的晴天"}],
        AgentConfig("demo-model"),
    )

    assert result["tool_calls"] == [
        {"name": "play_song", "args": {"song_name": "晴天", "artist": "周杰伦"}}
    ]
    assert "晴天" in result["reply"]
    assert context.memory.is_favorite("晴天") is False
    assert context.memory.get_play_history() == [
        {
            "song": "晴天",
            "artist": "周杰伦",
            "song_id": "demo-qq-1",
            "source": "qq",
        }
    ]


def test_demo_music_backend_returns_offline_audio_data_url():
    backend = DemoMusicBackend()
    songs = backend.search("周杰伦 晴天", source="qq", limit=6)

    assert songs[0]["name"] == "晴天"
    assert backend.song_url(songs[0]["id"], "qq").startswith("data:audio/wav;base64,")


def test_demo_mode_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert common.is_demo_mode() is False


def test_demo_mode_accepts_documented_truthy_values(monkeypatch):
    for value in ("1", "true", "yes", "on", "TRUE"):
        monkeypatch.setenv("DEMO_MODE", value)
        assert common.is_demo_mode() is True


def test_flask_app_starts_without_external_credentials_in_demo_mode():
    project_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DEMO_MODE"] = "1"
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("QQMUSIC_COOKIE", None)
    env.pop("WEATHER_API_KEY", None)
    env["PYTHONPATH"] = str(project_dir.parent / "agent-core" / "src")

    completed = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import app; "
                "response = app.app.test_client().get('/api/status'); "
                "print(type(app.client).__name__, response.json['mode'])"
            ),
        ],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr
    assert "DemoClient demo" in completed.stdout
