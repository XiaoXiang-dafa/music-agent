# -*- coding: utf-8 -*-
"""
播放工具 — 当用户想听某首歌时，Agent 调用它触发真实播放。

流程：搜索曲库 → 取最佳匹配 → 获取可播放地址 → 返回给前端播放。
"""
from __future__ import annotations

from .music import search_songs, get_song_url


def play_song(ctx, song_name: str, artist: str = "") -> dict:
    """用户想听某首 → 定位歌曲并返回可播放信息。

    优先 QQ 音乐；若拿不到可播放地址（如 JS 凭证过期），回退到网易云。
    """
    if not song_name or not str(song_name).strip():
        return {"error": "缺少歌名"}

    song_name = str(song_name).strip()
    kw = song_name if not artist else f"{song_name} {artist}"

    # 依次尝试音源，单个音源异常不阻断后续回退
    attempted_sources = []
    for source in ("qq", "netease"):
        attempted_sources.append(source)
        try:
            res = search_songs(ctx, kw, source=source)
            songs = res.get("songs", []) if isinstance(res, dict) else []
            if not songs:
                continue
            best = _pick_best(songs, song_name, artist)
            sid = best.get("id", "")
            url_res = get_song_url(ctx, sid, source=source)
            url = url_res.get("url", "") if isinstance(url_res, dict) else ""
        except Exception:
            continue

        if url:
            # 记入记忆（播放历史）
            try:
                ctx.memory.add_play(
                    song_name,
                    artist or best.get("artist", ""),
                    sid,
                    source,
                )
            except Exception:
                pass
            return {
                "song": best.get("name", song_name),
                "artist": best.get("artist", artist),
                "id": sid,
                "url": url,
                "cover": best.get("cover", ""),
                "source": source,
                "matched": True,
                "fallback_used": source != "qq",
                "attempted_sources": attempted_sources,
            }

    # 两个音源都拿不到地址，返回歌名但 url 为空
    return {
        "song": song_name,
        "artist": artist,
        "id": "",
        "url": "",
        "error": "未找到可播放版本",
        "matched": False,
        "fallback_used": False,
        "attempted_sources": attempted_sources,
    }


def _pick_best(songs: list[dict], song_name: str, artist: str) -> dict:
    """从搜索结果里选最匹配的一首。"""
    sn = song_name.lower().strip()
    ar = artist.lower().strip()
    best = songs[0]
    best_score = -1
    for s in songs:
        score = 0
        n = (s.get("name") or "").lower().strip()
        a = (s.get("artist") or "").lower().strip()
        if sn == n:
            score += 40
        elif sn in n:
            score += 25
        if ar and (ar in a or a in ar):
            score += 20
        score += len(n)
        if score > best_score:
            best_score = score
            best = s
    return best
