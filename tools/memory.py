# -*- coding: utf-8 -*-
"""
用户长期记忆 — 基于 SQLite 的会话隔离存储。

记录每个用户/会话的：
  - 收藏的歌
  - 音乐偏好描述（由 Agent 通过 remember_taste 写入）
  - 播放历史

供 Agent 通过 get_user_profile 检索并注入 Prompt，实现「越聊越懂你」。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS favorites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session TEXT NOT NULL,
  song TEXT NOT NULL,
  artist TEXT,
  song_id TEXT,
  created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS profile (
  session TEXT PRIMARY KEY,
  taste TEXT,
  updated INTEGER
);
CREATE TABLE IF NOT EXISTS play_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session TEXT NOT NULL,
  song TEXT NOT NULL,
  artist TEXT,
  song_id TEXT,
  source TEXT,
  created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fav_session ON favorites(session);
CREATE INDEX IF NOT EXISTS idx_play_session ON play_history(session);
"""


class UserMemory:
    """每个 session 一份独立记忆。"""

    def __init__(self, db_path: str, session_id: str):
        self.db_path = db_path
        self.session_id = session_id
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock, self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self):
        return sqlite3.connect(self.db_path, timeout=10)

    # ---- 收藏 ----
    def add_favorite(self, song: str, artist: str = "", song_id: str = "") -> int:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO favorites (session, song, artist, song_id, created) VALUES (?,?,?,?,?)",
                (self.session_id, song, artist, song_id, int(time.time())),
            )
            return cur.lastrowid

    def is_favorite(self, song: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM favorites WHERE session=? AND song=? LIMIT 1",
                (self.session_id, song),
            ).fetchone()
        return row is not None

    def get_favorites(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT song, artist, song_id FROM favorites "
                "WHERE session=? ORDER BY created DESC LIMIT ?",
                (self.session_id, limit),
            ).fetchall()
        return [{"song": r[0], "artist": r[1] or "", "song_id": r[2] or ""} for r in rows]

    # ---- 播放历史 ----
    def add_play(
        self,
        song: str,
        artist: str = "",
        song_id: str = "",
        source: str = "",
    ) -> int:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO play_history "
                "(session, song, artist, song_id, source, created) VALUES (?,?,?,?,?,?)",
                (
                    self.session_id,
                    song,
                    artist,
                    song_id,
                    source,
                    int(time.time()),
                ),
            )
            return cur.lastrowid

    def get_play_history(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT song, artist, song_id, source FROM play_history "
                "WHERE session=? ORDER BY created DESC, id DESC LIMIT ?",
                (self.session_id, max(0, int(limit))),
            ).fetchall()
        return [
            {
                "song": row[0],
                "artist": row[1] or "",
                "song_id": row[2] or "",
                "source": row[3] or "",
            }
            for row in rows
        ]

    def _play_history_count(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM play_history WHERE session=?",
                (self.session_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    # ---- 口味 ----
    def set_taste(self, taste: str):
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO profile (session, taste, updated) VALUES (?,?,?) "
                "ON CONFLICT(session) DO UPDATE SET taste=?, updated=?",
                (self.session_id, taste, int(time.time()), taste, int(time.time())),
            )

    def get_taste(self) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT taste FROM profile WHERE session=?", (self.session_id,)
            ).fetchone()
        return (row[0] or "") if row else ""

    # ---- 汇总（供 Agent/Prompt 注入） ----
    def get_profile_summary(self) -> dict:
        favorites = self.get_favorites()
        recent_plays = self.get_play_history()
        fav_text = "、".join(f"{f['song']}{'-' + f['artist'] if f['artist'] else ''}" for f in favorites[:10])
        recent_text = "、".join(
            f"{item['song']}{'-' + item['artist'] if item['artist'] else ''}"
            for item in recent_plays[:10]
        )
        return {
            "favorites_count": len(favorites),
            "favorites_text": fav_text or "（暂无收藏）",
            "play_history_count": self._play_history_count(),
            "recently_played_text": recent_text or "（暂无播放记录）",
            "taste": self.get_taste() or "（暂无偏好记录）",
        }

    def to_prompt_context(self) -> dict:
        s = self.get_profile_summary()
        return {
            "favorites": s["favorites_text"],
            "recently_played": s["recently_played_text"],
            "taste": s["taste"],
        }


# ---- 暴露给 Agent 的工具函数（第一个参数是 AgentContext） ----

def get_user_profile(ctx) -> dict:
    """查看用户的长期偏好/收藏/口味。"""
    return ctx.memory.get_profile_summary()


def save_favorite(ctx, song: str, artist: str = "") -> dict:
    """用户喜欢/想收藏某首歌时调用。"""
    if not song or not str(song).strip():
        return {"error": "缺少歌名"}
    song = str(song).strip()
    already = ctx.memory.is_favorite(song)
    if not already:
        ctx.memory.add_favorite(song, artist or "")
    return {"saved": True, "song": song, "artist": artist or "", "already": already}


def remember_taste(ctx, taste: str) -> dict:
    """记住用户的音乐偏好（供后续个性化推荐）。"""
    if not taste or not str(taste).strip():
        return {"error": "偏好描述为空"}
    taste = str(taste).strip()
    ctx.memory.set_taste(taste)
    return {"saved": True, "taste": taste}
