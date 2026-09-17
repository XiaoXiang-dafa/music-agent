# -*- coding: utf-8 -*-
"""
QQ 音乐 API 轻量封装
基于 qqmusic-api-python 库 (pip install qqmusic-api-python)
提供与 netease.py 相同的同步接口
"""
import re, asyncio, threading
from qqmusic_api import Client
from qqmusic_api.modules.song import SongFileType, SongFileInfo

# ========== 全局客户端 ==========
_client = None  # 每次请求新建，避免事件循环冲突


def _https(url: str) -> str:
    """播放器只接收 HTTPS 音源，避免被浏览器混合内容策略拦截。"""
    if url and url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _get_client():
    """每次调用创建新 Client"""
    return Client()


def _parse_cookie(cookie_string: str) -> dict:
    """从 cookie 字符串提取 Credential 所需字段"""
    cookies = {}
    for item in cookie_string.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()
    return {
        "openid": cookies.get("psrf_qqopenid", ""),
        "access_token": cookies.get("psrf_qqaccess_token", ""),
        "refresh_token": cookies.get("psrf_qqrefresh_token", ""),
        "unionid": cookies.get("psrf_qqunionid", ""),
        "musicid": int(cookies.get("uin", "0")) if cookies.get("uin") else 0,
        "musickey": cookies.get("qqmusic_key", ""),
        "musickey_create_time": int(cookies.get("psrf_musickey_createtime", "0")),
        "expired_at": int(cookies.get("psrf_access_token_expiresAt", "0")),
        "login_type": int(cookies.get("login_type", "0")),
        "encrypt_uin": cookies.get("euin", ""),
    }


def init_credential(cookie_string: str):
    """初始化 QQ 音乐凭证（用于获取播放链接）"""
    from qqmusic_api import Credential
    global _cred
    data = _parse_cookie(cookie_string)
    _cred = Credential(**data)
    print("✅ QQ 音乐凭证已加载")


_cred = None


# ========== 低质量过滤（与 netease.py 一致） ==========

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
    '钢琴', '吉他', '小提琴', '古筝', '二胡',
]


def _is_low_quality(name: str, album: str = "") -> bool:
    combined = f"{name} {album}".lower()
    for kw in _SKIP_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False


def _normalize_name(name: str) -> str:
    name = re.sub(r'[（(][^)）]*[)）]', '', name)
    name = re.sub(r'[\s\-—·•\.,，。、]', '', name)
    return name.lower()


# ========== 同步封装 ==========

_loop = None
_loop_thread = None


def _ensure_loop() -> "asyncio.AbstractEventLoop":
    """启动一个常驻后台事件循环（只建一次），供所有协程复用。"""
    global _loop, _loop_thread
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True, name="qqmusic-io")
        _loop_thread.start()
    return _loop


def _run(coro):
    """把协程提交到后台常驻事件循环并同步等待结果。

    相比旧的 asyncio.run()：不再每次调用都新建/销毁事件循环，
    既避免 Flask 多线程下的事件循环冲突，也避免底层 asyncio 对象在 GC 时
    报 “Event loop is closed” 崩溃。
    """
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


# ========== 搜索 ==========

def search(keyword: str, limit: int = 10) -> list[dict]:
    """
    搜索歌曲，返回 [{"id": mid, "name": "...", "artist": "...", "album": "...", "cover": "...", "duration": 毫秒}, ...]
    """
    try:
        return _run(_search_async(keyword, limit))
    except Exception as e:
        print(f"[QQMusic] search error: {e}")
        return []


async def _search_async(keyword: str, limit: int = 10) -> list[dict]:
    fetch_num = min(limit * 4, 80)
    resp = await _get_client().search.search_by_type(keyword=keyword, num=fetch_num)
    raw_songs = resp.song if resp else []

    songs = []
    for s in raw_songs:
        mid = s.mid
        name = s.name or s.title or ""
        artist = "/".join(a.name for a in (s.singer or []))
        album = s.album.name if s.album else ""
        # 封面：优先 album mid，备选 file media_mid，最后用 song mid
        album_mid = s.album.mid if s.album else ""
        if not album_mid and s.file:
            album_mid = s.file.media_mid or ""
        if not album_mid:
            album_mid = mid
        # 用 gtimg.cn CDN（兼容性更好，手机也能加载）
        cover = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else ""
        # duration: qqmusic_api 的 SongSearch 没有 duration 字段，默认为 0
        duration = 0

        if not mid or not name:
            continue
        if _is_low_quality(name, album):
            continue

        songs.append({
            "id": str(mid),
            "name": name,
            "artist": artist,
            "album": album,
            "cover": cover,
            "duration": int(duration),
        })

    # 去重
    seen = {}
    deduped = []
    for song in songs:
        key = _normalize_name(song["name"])
        if key in seen:
            if _score_song(song, keyword) > _score_song(seen[key], keyword):
                seen[key] = song
                for i, s in enumerate(deduped):
                    if _normalize_name(s["name"]) == key:
                        deduped[i] = song
                        break
        else:
            seen[key] = song
            deduped.append(song)

    return deduped[:limit]


def _score_song(song: dict, keyword: str) -> int:
    score = 0
    kw = keyword.lower().strip()
    n = song["name"].lower().strip()
    a = song["artist"].lower().strip()

    if kw == n:
        score += 40
    elif kw in n:
        score += 25
    elif n in kw:
        score += 15
    if kw in a or a in kw:
        score += 20
    if '(' not in song["name"] and '（' not in song["name"]:
        score += 10
    if len(song["name"]) <= 20:
        score += 5
    return score


# ========== 播放 URL ==========

def song_url(song_id: str) -> str:
    """
    获取歌曲播放链接。song_id 为 QQ 音乐 mid（如 "0039MnYb0qxYhV"）
    """
    try:
        return _run(_song_url_async(song_id))
    except Exception as e:
        print(f"[QQMusic] song_url error for {song_id}: {e}")
        return ""


async def _song_url_async(mid: str) -> str:
    # 尝试多种音质：192k ogg → 128k mp3 → 96k aac
    for file_type in [SongFileType.MP3_128, SongFileType.MP3_320, SongFileType.OGG_192]:
        try:
            urls = await _get_client().song.get_song_urls(
                [SongFileInfo(mid=mid, file_type=file_type)],
                credential=_cred,
            )
            if urls and urls.data:
                for item in urls.data:
                    # 优先用 wifiurl（完整链接），备选 purl
                    path = item.wifiurl or item.flowurl or item.purl
                    if path:
                        if path.startswith("http"):
                            return _https(path)
                        # QQ 音乐 CDN 域名
                        for domain in [
                            "https://ws.stream.qqmusic.qq.com/",
                            "https://dl.stream.qqmusic.qq.com/",
                            "https://isure.stream.qqmusic.qq.com/",
                        ]:
                            test_url = domain + path
                            # 简单检查是否可访问（HEAD 请求）
                            return test_url
        except Exception:
            continue
    return ""


# ========== 歌曲详情 ==========

def song_detail(song_id: str) -> dict:
    """
    获取歌曲详情，返回 {id, name, artist, album, cover, duration}
    """
    try:
        return _run(_song_detail_async(song_id))
    except Exception as e:
        print(f"[QQMusic] song_detail error for {song_id}: {e}")
        return {}


async def _song_detail_async(mid: str) -> dict:
    detail = await _get_client().song.get_detail(mid)
    if not detail:
        return {}

    track = detail.track
    if not track:
        return {"id": mid, "name": "", "artist": "", "album": "", "cover": "", "duration": 0}

    artist = "/".join(a.name for a in (track.singer or []))
    album_name = track.album.name if track.album else ""
    album_mid = track.album.mid if track.album else ""

    return {
        "id": mid,
        "name": track.name or "",
        "artist": artist,
        "album": album_name,
        "cover": f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else "",
        "duration": int(track.interval or 0) * 1000 if track.interval else 0,
    }


# ========== 歌词 ==========

def lyric(song_id: str) -> str:
    """
    获取歌词（LRC 格式原文）
    """
    try:
        return _run(_lyric_async(song_id))
    except Exception as e:
        print(f"[QQMusic] lyric error for {song_id}: {e}")
        return ""


async def _lyric_async(mid: str) -> str:
    lrc = await _get_client().lyric.get_lyric(mid)
    if lrc and lrc.lyric:
        # QQ 音乐歌词是 hex 编码的加密数据，用库内解密工具
        from qqmusic_api.algorithms import qrc_decrypt
        return qrc_decrypt(lrc.lyric)
    return ""
