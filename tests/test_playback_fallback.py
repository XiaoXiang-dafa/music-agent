from types import SimpleNamespace

from tools import playback


class MemorySpy:
    def __init__(self):
        self.saved = []
        self.played = []

    def add_favorite(self, song, artist="", song_id=""):
        self.saved.append((song, artist, song_id))

    def add_play(self, song, artist="", song_id="", source=""):
        self.played.append((song, artist, song_id, source))


def _context():
    return SimpleNamespace(memory=MemorySpy())


def test_qq_exception_falls_back_to_netease(monkeypatch):
    searched = []

    def fake_search(_ctx, _keyword, source):
        searched.append(source)
        return {
            "songs": [
                {
                    "id": f"{source}-sunny-day",
                    "name": "晴天",
                    "artist": "周杰伦",
                    "cover": "",
                }
            ]
        }

    def fake_url(_ctx, _song_id, source):
        if source == "qq":
            raise RuntimeError("QQ credential expired")
        return {"url": "https://example.invalid/demo.mp3"}

    monkeypatch.setattr(playback, "search_songs", fake_search)
    monkeypatch.setattr(playback, "get_song_url", fake_url)
    context = _context()

    result = playback.play_song(context, "晴天", "周杰伦")

    assert searched == ["qq", "netease"]
    assert result["source"] == "netease"
    assert result["fallback_used"] is True
    assert result["attempted_sources"] == ["qq", "netease"]
    assert context.memory.played == [
        ("晴天", "周杰伦", "netease-sunny-day", "netease")
    ]
    assert context.memory.saved == []


def test_both_sources_fail_with_complete_attempt_history(monkeypatch):
    searched = []

    def empty_search(_ctx, _keyword, source):
        searched.append(source)
        return {"songs": []}

    monkeypatch.setattr(playback, "search_songs", empty_search)
    context = _context()

    result = playback.play_song(context, "不存在的歌", "")

    assert searched == ["qq", "netease"]
    assert result["matched"] is False
    assert result["attempted_sources"] == ["qq", "netease"]
    assert result["fallback_used"] is False
    assert context.memory.played == []
    assert context.memory.saved == []
