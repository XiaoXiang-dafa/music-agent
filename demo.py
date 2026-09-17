# -*- coding: utf-8 -*-
"""离线演示运行时：替代外部 LLM 与音乐 API，但保留真实 Agent 编排。"""
from __future__ import annotations

import base64
import io
import json
import math
import wave
from functools import lru_cache
from types import SimpleNamespace


DEMO_TRACKS = (
    {"name": "晴天", "artist": "周杰伦", "cover": "", "duration": 240},
    {"name": "七里香", "artist": "周杰伦", "cover": "", "duration": 299},
    {"name": "平凡之路", "artist": "朴树", "cover": "", "duration": 301},
)


@lru_cache(maxsize=1)
def _demo_audio_data_url() -> str:
    """生成短提示音，证明播放器链路可用且无需下载音频文件。"""
    sample_rate = 8000
    frame_count = sample_rate // 4
    frames = bytes(
        int(128 + 22 * math.sin(2 * math.pi * 440 * index / sample_rate))
        for index in range(frame_count)
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(sample_rate)
        audio.writeframes(frames)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


class DemoMusicBackend:
    """确定性的本地曲库 fixture。"""

    def search(self, keyword: str, source: str, limit: int = 6) -> list[dict]:
        normalized = str(keyword).lower().replace(" ", "")
        matches = [
            track
            for track in DEMO_TRACKS
            if track["name"].lower() in normalized or track["artist"].lower() in normalized
        ]
        return [
            {**track, "id": f"demo-{source}-{index}", "source": source}
            for index, track in enumerate(matches[:limit], start=1)
        ]

    def song_url(self, song_id: str, source: str) -> str:
        if not str(song_id).startswith(f"demo-{source}-"):
            return ""
        return _demo_audio_data_url()

    def lyric(self, song_id: str, source: str) -> str:
        if not str(song_id).startswith(f"demo-{source}-"):
            return ""
        return "[Demo] 离线模式不提供真实歌词。"


class DemoMusicRecommender:
    """不访问 LLM 的固定演示歌单。"""

    def get_daily_songs(self, weather_info: str = "", custom_taste: str = "") -> list[dict]:
        return [
            {"song": track["name"], "artist": track["artist"], "reason": "离线 Demo 推荐"}
            for track in DEMO_TRACKS
        ]

    @staticmethod
    def format_music_block(songs: list[dict]) -> str:
        lines = ["🎵 离线 Demo 歌单"]
        lines.extend(
            f"{index}. {song['song']} - {song['artist']}：{song['reason']}"
            for index, song in enumerate(songs, start=1)
        )
        return "\n".join(lines)


def _chunk(content=None, tool_calls=None, finish_reason=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
            )
        ]
    )


def _message_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))]
    )


class _DemoCompletions:
    def create(self, *, messages, stream=False, **_kwargs):
        response = self._next_response(messages)
        if response["type"] == "tool":
            tool_call = SimpleNamespace(
                index=0,
                id="demo_call_1",
                function=SimpleNamespace(
                    name=response["name"],
                    arguments=json.dumps(response["arguments"], ensure_ascii=False),
                ),
            )
            if stream:
                return iter([_chunk(tool_calls=[tool_call], finish_reason="tool_calls")])
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=None, tool_calls=[tool_call]),
                        finish_reason="tool_calls",
                    )
                ]
            )

        content = response["content"]
        if not stream:
            return _message_response(content)
        parts = [content[index:index + 8] for index in range(0, len(content), 8)] or [""]
        return iter(
            _chunk(content=part, finish_reason="stop" if index == len(parts) - 1 else None)
            for index, part in enumerate(parts)
        )

    def _next_response(self, messages: list[dict]) -> dict:
        if messages and messages[-1].get("role") == "tool":
            try:
                result = json.loads(messages[-1].get("content") or "{}")
            except json.JSONDecodeError:
                result = {}
            if result.get("matched"):
                source = "QQ 音乐" if result.get("source") == "qq" else "网易云"
                return {
                    "type": "text",
                    "content": f"已经为你找到《{result.get('song', '')}》—{result.get('artist', '')}，命中{source}。",
                }
            return {"type": "text", "content": "两个音源都没有找到可播放版本，换首歌试试吧。"}

        user_text = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "user"),
            "",
        )
        for track in DEMO_TRACKS:
            if track["name"] in user_text:
                return {
                    "type": "tool",
                    "name": "play_song",
                    "arguments": {"song_name": track["name"], "artist": track["artist"]},
                }
        return {
            "type": "text",
            "content": "离线 Demo 已就绪。你可以说：我想听周杰伦的晴天。",
        }


class DemoClient:
    """提供 `client.chat.completions.create` 兼容接口。"""

    def __init__(self):
        self.chat = SimpleNamespace(completions=_DemoCompletions())
