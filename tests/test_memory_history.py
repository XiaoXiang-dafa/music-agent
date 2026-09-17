from types import SimpleNamespace

from agent.prompts import build_system_prompt
from tools.memory import UserMemory, save_favorite


def test_play_is_history_not_favorite_and_schema_is_idempotent(tmp_path):
    db_path = str(tmp_path / "memory.db")
    memory = UserMemory(db_path, "session-a")
    memory.add_play("晴天", "周杰伦", "qq-1", "qq")

    reopened = UserMemory(db_path, "session-a")

    assert reopened.get_play_history() == [
        {
            "song": "晴天",
            "artist": "周杰伦",
            "song_id": "qq-1",
            "source": "qq",
        }
    ]
    assert reopened.get_favorites() == []


def test_play_history_is_isolated_by_session_and_respects_limit(tmp_path):
    db_path = str(tmp_path / "memory.db")
    session_a = UserMemory(db_path, "session-a")
    session_b = UserMemory(db_path, "session-b")
    session_a.add_play("晴天", "周杰伦", "qq-1", "qq")
    session_a.add_play("稻香", "周杰伦", "netease-2", "netease")
    session_b.add_play("后来", "刘若英", "qq-3", "qq")

    assert session_a.get_play_history(limit=1) == [
        {
            "song": "稻香",
            "artist": "周杰伦",
            "song_id": "netease-2",
            "source": "netease",
        }
    ]
    assert session_b.get_play_history() == [
        {
            "song": "后来",
            "artist": "刘若英",
            "song_id": "qq-3",
            "source": "qq",
        }
    ]


def test_profile_and_prompt_keep_favorites_separate_from_recent_plays(tmp_path):
    memory = UserMemory(str(tmp_path / "memory.db"), "session-a")
    memory.add_favorite("七里香", "周杰伦", "fav-1")
    memory.add_play("晴天", "周杰伦", "qq-1", "qq")

    summary = memory.get_profile_summary()
    context = memory.to_prompt_context()
    prompt = build_system_prompt(
        "你是测试角色",
        "测试角色",
        favorites=context["favorites"],
        taste=context["taste"],
        recently_played=context["recently_played"],
    )

    assert summary["play_history_count"] == 1
    assert summary["recently_played_text"] == "晴天-周杰伦"
    assert context["recently_played"] == "晴天-周杰伦"
    assert "用户主动收藏：七里香-周杰伦" in prompt
    assert "最近播放：晴天-周杰伦" in prompt
    assert "避免短期内重复推荐" in prompt


def test_save_favorite_remains_the_explicit_favorite_writer(tmp_path):
    memory = UserMemory(str(tmp_path / "memory.db"), "session-a")
    context = SimpleNamespace(memory=memory)

    result = save_favorite(context, "晴天", "周杰伦")

    assert result == {
        "saved": True,
        "song": "晴天",
        "artist": "周杰伦",
        "already": False,
    }
    assert memory.get_favorites() == [
        {"song": "晴天", "artist": "周杰伦", "song_id": ""}
    ]
    assert memory.get_play_history() == []
