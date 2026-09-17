# -*- coding: utf-8 -*-
"""
网易云音乐 API 轻量封装
直接 HTTP 调用，不依赖第三方包
"""
import requests
import json
import re

BASE = "https://music.163.com/api"

def _https(url: str) -> str:
    """网易云CDN图片链接 HTTP → HTTPS（否则小程序显示不了）"""
    if url and url.startswith("http://"):
        return url.replace("http://", "https://", 1)
    return url
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    "Referer": "https://music.163.com/",
}

# 低质量版本关键词（出现在歌名或专辑名中则过滤）
_SKIP_KEYWORDS = [
    '翻唱', 'cover', 'Cover',
    'Live', 'live', '现场', '演唱会', '音乐会', 'concert',
    '伴奏', 'instrumental', 'karaoke', '纯音乐',
    'DJ', 'dj', 'Remix', 'remix', '混音', '串烧',
    '铃声', 'ringtone',
    'Demo', 'demo',
    '重制', '重置',
    '抖音', 'TikTok',
    '修复', '修复版',
    '降调', '升调',
    '变速',
    '教学', '教程',
    '钢琴', '吉他', '小提琴', '古筝', '二胡',  # 纯器乐翻奏
]


def _is_low_quality(song: dict) -> bool:
    """判断是否为低质量/翻唱/现场等非原版歌曲"""
    name = song.get("name", "")
    album = song.get("al", {}).get("name", "")
    combined = f"{name} {album}".lower()

    for kw in _SKIP_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False


def _normalize_name(name: str) -> str:
    """规范化歌名用于去重比较"""
    # 去掉括号内容（版本标记）
    name = re.sub(r'[（(][^)）]*[)）]', '', name)
    # 去空格和标点
    name = re.sub(r'[\s\-—·•\.,，。、]', '', name)
    return name.lower()


def search(keyword: str, limit: int = 10) -> list[dict]:
    """
    搜索歌曲并过滤去重
    返回 [{"id": xxx, "name": "晴天", "artist": "周杰伦", "album": "...", "cover": "..."}, ...]
    """
    try:
        # 多拉一些结果用于过滤
        fetch_limit = min(limit * 4, 80)
        resp = requests.post(
            "https://music.163.com/api/cloudsearch/pc",
            data={"s": keyword, "type": 1, "limit": fetch_limit, "offset": 0},
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()
        raw_songs = data.get("result", {}).get("songs", [])

        # Step 1: 构建结果 + 过滤低质量版本
        results = []
        for s in raw_songs:
            # 跳过收费过高的（fee=8 是付费专辑，fee=4 是专辑专享）
            fee = s.get("fee", 0)
            if fee >= 4:
                continue

            artists = [a["name"] for a in s.get("ar", [])]
            artist_str = "/".join(artists)

            song = {
                "id": s["id"],
                "name": s["name"],
                "artist": artist_str,
                "album": s.get("al", {}).get("name", ""),
                "cover": _https(s.get("al", {}).get("picUrl", "")),
                "duration": s.get("dt", 0),
                "_fee": fee,
            }

            # 过滤低质量
            if _is_low_quality(song):
                continue

            results.append(song)

        # Step 2: 去重 — 同名歌保留最匹配的版本
        seen = {}
        deduped = []
        for song in results:
            key = _normalize_name(song["name"])
            if key in seen:
                existing = seen[key]
                # 保留更优的：原唱优先、歌名最干净的优先
                current_score = _score_song(song, keyword)
                existing_score = _score_song(existing, keyword)
                if current_score > existing_score:
                    seen[key] = song
                    # 替换 deduped 中的旧条目
                    for i, s in enumerate(deduped):
                        if _normalize_name(s["name"]) == key:
                            deduped[i] = song
                            break
            else:
                seen[key] = song
                deduped.append(song)

        return deduped[:limit]

    except Exception as e:
        print(f"[Netease] search error: {e}")
        return []


def _score_song(song: dict, keyword: str) -> int:
    """评分歌曲：越匹配关键词、越像原版分越高"""
    score = 0
    kw_lower = keyword.lower().strip()
    name_lower = song["name"].lower().strip()
    artist_lower = song["artist"].lower().strip()

    # 歌名精确匹配
    if kw_lower == name_lower:
        score += 40
    elif kw_lower in name_lower:
        score += 25
    elif name_lower in kw_lower:
        score += 15

    # 关键词里带歌手名 → 歌手匹配加分
    if kw_lower in artist_lower or artist_lower in kw_lower:
        score += 20

    # 歌名不要太长（包含括号/额外标记的通常不是原版）
    if '(' not in song["name"] and '（' not in song["name"]:
        score += 10
    if len(song["name"]) <= 20:
        score += 5

    # 免费歌曲优先
    if song.get("_fee", 0) == 0:
        score += 5

    return score


def song_url(song_id: int) -> str:
    """
    获取歌曲播放链接 尝试多个音质 取最高可用
    """
    # 从高到低尝试
    for br in [999000, 320000, 192000, 128000]:
        try:
            resp = requests.post(
                f"{BASE}/song/enhance/player/url",
                data={"ids": json.dumps([song_id]), "br": br},
                headers=HEADERS, timeout=10,
            )
            data = resp.json()
            for d in data.get("data", []):
                url = d.get("url", "")
                if url:
                    return url
        except Exception:
            continue
    return ""


def song_detail(song_id: int) -> dict:
    """
    获取歌曲详情 返回 {name, artist, album, cover, duration}
    """
    try:
        resp = requests.post(
            f"{BASE}/song/detail",
            data={"ids": json.dumps([song_id])},
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()
        s = data.get("songs", [{}])[0]
        return {
            "id": s.get("id"),
            "name": s.get("name", ""),
            "artist": "/".join(a["name"] for a in s.get("ar", [])),
            "album": s.get("al", {}).get("name", ""),
            "cover": _https(s.get("al", {}).get("picUrl", "")),
            "duration": s.get("dt", 0),
        }
    except Exception as e:
        print(f"[Netease] detail error: {e}")
        return {}


def lyric(song_id: int) -> str:
    """
    获取歌词 返回带时间标记的原始lrc
    """
    try:
        resp = requests.post(
            f"{BASE}/song/lyric",
            data={"id": song_id, "lv": 1, "kv": 1, "tv": -1},
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()
        return data.get("lrc", {}).get("lyric", "")
    except Exception as e:
        print(f"[Netease] lyric error: {e}")
        return ""
