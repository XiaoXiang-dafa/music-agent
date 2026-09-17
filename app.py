#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, re, threading, requests as http_requests, locale, logging
from collections import defaultdict, deque
# 强制 UTF-8 编码（解决 macOS 终端 ASCI 编码导致的 crash）
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
try: locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except: pass
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
from datetime import datetime
from time import monotonic, perf_counter_ns
from urllib.parse import urlsplit
from flask import Flask, request, jsonify, send_from_directory, Response

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIST_DIR = os.path.join(BOT_DIR, "web", "dist")
sys.path.insert(0, os.path.join(BOT_DIR, "modules"))

from openai import OpenAI
from character import CharacterManager
from weather import WeatherService
from music import MusicRecommender
from qqmusic import search as qqmusic_search, song_url, lyric, init_credential
from netease import search as netease_search, song_url as netease_song_url, lyric as netease_lyric
from common import resolve_api_keys, require_deepseek_api_key, is_configured_secret, is_demo_mode, morning_greeting, weather_hint, build_morning_message
from demo import DemoClient, DemoMusicBackend, DemoMusicRecommender

# ===== Agent 核心 & 工具 =====
from agent import AgentConfig, run_agent, stream_agent
from agent.prompts import build_system_prompt
from tools import AgentContext, build_registry
from tools.memory import UserMemory
from observability import TraceRecorder

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

MAX_MESSAGE_LENGTH = 4000
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CHAT_RATE_LIMIT = 20
CHAT_RATE_WINDOW_SECONDS = 60
_rate_buckets = defaultdict(deque)
_rate_lock = threading.Lock()


@app.before_request
def protect_chat_endpoints():
    if request.path not in {"/api/chat", "/api/chat/stream"}:
        return None

    now = monotonic()
    key = request.remote_addr or "unknown"
    with _rate_lock:
        bucket = _rate_buckets[key]
        while bucket and now - bucket[0] >= CHAT_RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= CHAT_RATE_LIMIT:
            response = jsonify({"error": "rate limit exceeded"})
            response.status_code = 429
            response.headers["Retry-After"] = str(CHAT_RATE_WINDOW_SECONDS)
            return response
        bucket.append(now)
    return None

@app.after_request
def set_utf8_charset(resp):
    ct = resp.headers.get('Content-Type', '')
    if 'application/json' in ct and 'charset' not in ct:
        resp.headers['Content-Type'] = ct + '; charset=utf-8'
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; "
        "media-src 'self' data: https:; connect-src 'self'; "
        "style-src 'self'; script-src 'self'"
    )
    return resp

# 全局组件（lazy init）
client = None
char_mgr = None
weather_svc = None
music_rec = None
config = None
demo_mode = False
demo_music_backend = None
chat_histories = {}   # session -> history list
_chat_lock = threading.Lock()
trace_recorder = TraceRecorder(os.path.join(BOT_DIR, "data", "traces.db"))
_logger = logging.getLogger(__name__)

# 用户长期记忆（按 session 缓存 UserMemory 实例）
_memories = {}
_mem_lock = threading.Lock()
MEMORY_DB = os.path.join(BOT_DIR, "data", "memory.db")


def _get_memory(session_id: str) -> UserMemory:
    with _mem_lock:
        if session_id not in _memories:
            _memories[session_id] = UserMemory(MEMORY_DB, session_id)
        return _memories[session_id]


def _build_context(session_id: str) -> AgentContext:
    """为一次 Agent 请求组装上下文（绑定用户记忆 + 全局服务）。"""
    return AgentContext(
        client=client,
        model=config["deepseek"]["model"],
        memory=_get_memory(session_id),
        session_id=session_id,
        weather_svc=weather_svc,
        music_rec=music_rec,
        char_mgr=char_mgr,
        extra={"music_backend": demo_music_backend} if demo_music_backend else {},
    )


def _agent_tools(session_id: str):
    return build_registry(_build_context(session_id))


def _build_system(session_id: str, weather_hint_str: str = "") -> str:
    """组装当前角色的 system prompt（人设 + 工具说明 + 用户记忆）。"""
    persona = char_mgr.get_prompt()
    name = char_mgr.get_current()["name"]
    mem = _get_memory(session_id).to_prompt_context()
    return build_system_prompt(
        persona,
        name,
        mem["favorites"],
        mem["taste"],
        weather_hint_str,
        recently_played=mem["recently_played"],
    )


def _trace_start(session_id: str) -> str:
    try:
        return trace_recorder.start_run(session_id, "demo" if demo_mode else "live")
    except Exception:
        _logger.exception("trace start failed")
        return ""


def _trace_record_tool(trace_id: str, sequence: int, event: dict) -> None:
    if not trace_id:
        return
    try:
        trace_recorder.record_tool(
            trace_id,
            sequence,
            event.get("call_id", ""),
            event.get("name", ""),
            event.get("status", "success"),
            event.get("duration_ms", 0),
            event.get("result"),
        )
    except Exception:
        _logger.exception("trace tool event failed")


def _trace_finish(
    trace_id: str,
    status: str,
    steps: int,
    tool_call_count: int,
    started_ns: int,
    error_type: str | None = None,
) -> None:
    if not trace_id:
        return
    try:
        duration_ms = max(0, (perf_counter_ns() - started_ns) // 1_000_000)
        trace_recorder.finish_run(
            trace_id, status, steps, tool_call_count, duration_ms, error_type
        )
    except Exception:
        _logger.exception("trace finish failed")


def _sse(event: str, data: dict) -> str:
    """把事件转成 SSE 格式。"""
    import json as _json
    return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_chat_payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, None, (jsonify({"error": "invalid request"}), 400)

    user_msg = data.get("message", "")
    session_id = data.get("session", "default")
    if not isinstance(user_msg, str) or not isinstance(session_id, str):
        return None, None, (jsonify({"error": "invalid request"}), 400)

    user_msg = user_msg.strip()
    session_id = session_id.strip()
    if len(user_msg) > MAX_MESSAGE_LENGTH:
        return None, None, (jsonify({"error": "message too long"}), 400)
    if not SESSION_ID_RE.fullmatch(session_id):
        return None, None, (jsonify({"error": "invalid session"}), 400)
    return user_msg, session_id, None


def init():
    global client, char_mgr, weather_svc, music_rec, config, demo_mode, demo_music_backend
    with open(os.path.join(BOT_DIR, "config.json"), encoding="utf-8") as f:
        config = json.load(f)

    # 环境变量覆盖敏感值
    resolve_api_keys(config)
    if os.environ.get("QQMUSIC_COOKIE"):
        config.setdefault("qqmusic", {})["cookie"] = os.environ["QQMUSIC_COOKIE"]

    cfg = config["deepseek"]
    demo_mode = is_demo_mode()
    if demo_mode:
        client = DemoClient()
        demo_music_backend = DemoMusicBackend()
    else:
        require_deepseek_api_key(config)
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["api_base"])
        demo_music_backend = None

    char_mgr = CharacterManager(client, cfg["model"], os.path.join(BOT_DIR, "data"))

    wcfg = config.get("weather", {})
    if is_configured_secret(wcfg.get("api_key")):
        weather_svc = WeatherService(wcfg["api_key"], config["schedule"].get("weather_city", "auto"))

    music_rec = DemoMusicRecommender() if demo_mode else MusicRecommender(client, cfg["model"], weather_svc)

    # 初始化 QQ 音乐凭证
    qq_cookie = config.get("qqmusic", {}).get("cookie", "")
    if not demo_mode and is_configured_secret(qq_cookie):
        init_credential(qq_cookie)
    elif not demo_mode:
        print("⚠️ QQ 音乐 Cookie 未配置，搜索/播放功能可能不可用")


# ===== API Routes =====

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(BOT_DIR, "static"), filename)


@app.route("/assets/<path:filename>")
def web_assets(filename):
    return send_from_directory(os.path.join(WEB_DIST_DIR, "assets"), filename)


@app.route("/")
def index():
    index_file = os.path.join(WEB_DIST_DIR, "index.html")
    if not os.path.isfile(index_file):
        return Response(
            "前端尚未构建，请先运行：cd web && npm run build",
            status=503,
            mimetype="text/plain",
        )
    return send_from_directory(WEB_DIST_DIR, "index.html")


@app.route("/api/status")
def status():
    """获取当前状态"""
    c = char_mgr.get_current()
    weather_info = ""
    if weather_svc:
        w = weather_svc.get_weather()
        if "error" not in w:
            weather_info = weather_hint(w)
    return jsonify({
        "character": {"name": c["name"], "type": c.get("type", ""), "speaking_style": c.get("speaking_style", "")},
        "characters": char_mgr.list_characters(),
        "weather": weather_info,
        "mode": "demo" if demo_mode else "live",
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """通过 Agent 获取回复（按 session 隔离会话和历史，保持小程序兼容）。"""
    user_msg, session_id, error = _parse_chat_payload()
    if error is not None:
        return error

    if not user_msg:
        return jsonify({"reply": "说点什么吧"})

    trace_id = _trace_start(session_id)
    trace_started_ns = perf_counter_ns()

    with _chat_lock:
        history = list(chat_histories.get(session_id, []))

    messages = list(history[-30:]) + [{"role": "user", "content": user_msg}]

    try:
        reg = _agent_tools(session_id)
        system_prompt = _build_system(session_id)
        cfg = AgentConfig(model=config["deepseek"]["model"], temperature=0.8, max_steps=6, max_tokens=600)
        result = run_agent(client, reg, system_prompt, messages, cfg)
        for sequence, tool_event in enumerate(result.get("tool_results", []), 1):
            _trace_record_tool(trace_id, sequence, tool_event)
        reply = result["reply"] or "……"

        # 从工具调用中识别播放意图（兼容小程序）
        play = None
        for tc in result["tool_calls"]:
            if tc["name"] == "play_song":
                args = tc["args"]
                play = {"song": args.get("song_name", ""), "artist": args.get("artist", "")}
                break

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        if len(history) > 30:
            history = history[-30:]
        with _chat_lock:
            chat_histories[session_id] = history

        _trace_finish(
            trace_id,
            "truncated" if result.get("truncated") else "success",
            result.get("steps", 0),
            len(result.get("tool_results", [])),
            trace_started_ns,
        )
        return jsonify({
            "reply": reply,
            "character": char_mgr.get_current()["name"],
            "play": play,
            "steps": result["steps"],
            "tool_calls": result["tool_calls"],
            "trace_id": trace_id,
        })
    except Exception as e:
        _trace_finish(trace_id, "error", 0, 0, trace_started_ns, type(e).__name__)
        _logger.exception("chat request failed")
        return jsonify({"reply": "处理请求时发生错误", "character": "系统", "trace_id": trace_id}), 500


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """SSE 流式 Agent 对话（Web 演示端）：流式返回工具调用过程与回复 token。"""
    user_msg, session_id, error = _parse_chat_payload()
    if error is not None:
        return error
    trace_id = _trace_start(session_id)
    trace_started_ns = perf_counter_ns()

    with _chat_lock:
        history = list(chat_histories.get(session_id, []))

    def gen():
        if not user_msg:
            _trace_finish(trace_id, "success", 0, 0, trace_started_ns)
            yield _sse("done", {"reply": "说点什么吧", "steps": 0, "empty": True, "trace_id": trace_id, "status": "success", "duration_ms": 0})
            return
        try:
            reg = _agent_tools(session_id)
            system_prompt = _build_system(session_id)
            cfg = AgentConfig(model=config["deepseek"]["model"], temperature=0.8, max_steps=6, max_tokens=600)
            messages = list(history[-30:]) + [{"role": "user", "content": user_msg}]

            yield _sse("start", {"session": session_id, "character": char_mgr.get_current()["name"], "trace_id": trace_id, "mode": "demo" if demo_mode else "live"})

            reply = ""
            steps = 0
            tool_sequence = 0
            truncated = False
            for ev in stream_agent(client, reg, system_prompt, messages, cfg):
                if ev["type"] == "reply_chunk":
                    reply += ev["content"]
                    yield _sse("reply_chunk", {"content": ev["content"]})
                elif ev["type"] == "tool_call":
                    yield _sse("tool_call", {"name": ev["name"], "args": ev["args"], "trace_id": trace_id, "call_id": ev.get("call_id", "")})
                elif ev["type"] == "tool_result":
                    tool_sequence += 1
                    _trace_record_tool(trace_id, tool_sequence, ev)
                    yield _sse("tool_result", {"name": ev["name"], "result": ev["result"], "trace_id": trace_id, "call_id": ev.get("call_id", ""), "status": ev.get("status", "success"), "duration_ms": ev.get("duration_ms", 0)})
                elif ev["type"] == "done":
                    steps = ev.get("steps", steps)
                    truncated = ev.get("truncated", False)

            # 保存历史
            new_history = list(history)
            new_history.append({"role": "user", "content": user_msg})
            new_history.append({"role": "assistant", "content": reply})
            if len(new_history) > 30:
                new_history = new_history[-30:]
            with _chat_lock:
                chat_histories[session_id] = new_history

            trace_status = "truncated" if truncated else "success"
            _trace_finish(trace_id, trace_status, steps, tool_sequence, trace_started_ns)
            duration_ms = max(0, (perf_counter_ns() - trace_started_ns) // 1_000_000)
            yield _sse("done", {"reply": reply, "steps": steps, "truncated": truncated, "trace_id": trace_id, "status": trace_status, "duration_ms": duration_ms})
        except Exception as e:
            _trace_finish(trace_id, "error", steps if "steps" in locals() else 0, tool_sequence if "tool_sequence" in locals() else 0, trace_started_ns, type(e).__name__)
            yield _sse("error", {"message": "处理请求时发生错误", "trace_id": trace_id})

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.route("/api/traces")
def api_traces():
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    return jsonify(trace_recorder.list_runs(limit))


@app.route("/api/traces/<trace_id>")
def api_trace_detail(trace_id):
    detail = trace_recorder.get_run(trace_id)
    if detail is None:
        return jsonify({"error": "trace not found"}), 404
    return jsonify(detail)


@app.route("/api/tools")
def api_tools():
    """列出 Agent 可用工具（供演示前端展示工具目录）。"""
    reg = _agent_tools("__catalog__")
    return jsonify({"tools": reg.list_descriptions()})


@app.route("/api/music")
def music():
    """获取今日歌单"""
    wh = ""
    if weather_svc:
        w = weather_svc.get_weather()
        wh = weather_hint(w)

    taste = char_mgr.get_music_taste()
    songs = music_rec.get_daily_songs(wh, taste)
    block = music_rec.format_music_block(songs)
    return jsonify({"songs": block, "character": char_mgr.get_current()["name"]})


@app.route("/api/morning")
def morning():
    """获取完整早安消息"""
    greeting = morning_greeting()
    weather_part, wh = build_morning_message(weather_svc, greeting)

    # 歌单
    music_part = ""
    try:
        taste = char_mgr.get_music_taste()
        songs = music_rec.get_daily_songs(wh, taste)
        music_part = music_rec.format_music_block(songs)
    except Exception:
        pass

    full = f"{weather_part}\n\n{music_part}" if music_part else weather_part
    return jsonify({"message": full})


# ===== 封面主色提取 =====

_ALLOWED_COVER_HOSTS = ("y.gtimg.cn", "music.126.net")
_MAX_COVER_BYTES = 2 * 1024 * 1024
_MAX_COVER_PIXELS = 10_000_000


def _is_allowed_cover_url(raw_url: str) -> bool:
    try:
        parsed = urlsplit(raw_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        return False
    if port not in (None, 443):
        return False
    return any(
        hostname == allowed or hostname.endswith(f".{allowed}")
        for allowed in _ALLOWED_COVER_HOSTS
    )


def _download_cover(raw_url: str) -> bytes:
    response = http_requests.get(
        raw_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://y.qq.com/"},
        timeout=(3, 8),
        allow_redirects=False,
        stream=True,
    )
    try:
        if response.status_code != 200:
            return b""
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_COVER_BYTES:
            raise ValueError("cover is too large")
        chunks = []
        total = 0
        for chunk in response.iter_content(64 * 1024):
            total += len(chunk)
            if total > _MAX_COVER_BYTES:
                raise ValueError("cover is too large")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        response.close()

@app.route("/api/cover/color")
def api_cover_color():
    """从封面提取主色调，用于播放器背景"""
    cover_url = request.args.get("url", "")
    if not cover_url:
        return jsonify({"color": None})
    if not _is_allowed_cover_url(cover_url):
        return jsonify({"error": "invalid cover url", "color": None}), 400

    try:
        from PIL import Image
        from io import BytesIO
        import warnings

        raw_image = _download_cover(cover_url)
        if not raw_image:
            return jsonify({"color": None})

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            img = Image.open(BytesIO(raw_image))
        if img.width * img.height > _MAX_COVER_PIXELS:
            img.close()
            return jsonify({"error": "cover image too large", "color": None}), 413
        img = img.convert("RGB")
        img = img.resize((80, 80))

        pixels = list(img.getdata())
        # 加权平均：饱和度高的像素权重更高，避免灰暗色
        r_sum = g_sum = b_sum = total_weight = 0.0
        for pr, pg, pb in pixels:
            saturation = max(pr, pg, pb) - min(pr, pg, pb)
            w = 1.0 + saturation / 255.0  # 高饱和像素权重可达 2x
            r_sum += pr * w
            g_sum += pg * w
            b_sum += pb * w
            total_weight += w

        avg_r = int(r_sum / total_weight)
        avg_g = int(g_sum / total_weight)
        avg_b = int(b_sum / total_weight)

        return jsonify({"color": {"r": avg_r, "g": avg_g, "b": avg_b}})
    except Exception as e:
        print(f"[Color] 提取失败: {e}")
        return jsonify({"color": None})


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"songs": []})
    if len(q) > 200:
        return jsonify({"error": "query too long", "songs": []}), 400
    limit = _search_limit()
    if limit is None:
        return jsonify({"error": "invalid limit", "songs": []}), 400
    songs = qqmusic_search(q, limit=limit)
    return jsonify({"songs": songs})


@app.route("/api/song/url")
def api_song_url():
    sid = request.args.get("id", "")
    if not sid:
        return jsonify({"url": ""})
    url = song_url(sid)
    return jsonify({"url": url})


@app.route("/api/lyric")
def api_lyric():
    sid = request.args.get("id", "")
    if not sid:
        return jsonify({"lyric": ""})
    lrc = lyric(sid)
    return jsonify({"lyric": lrc})


# ===== 网易云音乐 API =====


def _search_limit(default: int = 15, maximum: int = 30):
    raw = request.args.get("limit", str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 1:
        return None
    return min(value, maximum)

@app.route("/api/search/netease")
def api_search_netease():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"songs": []})
    if len(q) > 200:
        return jsonify({"error": "query too long", "songs": []}), 400
    limit = _search_limit()
    if limit is None:
        return jsonify({"error": "invalid limit", "songs": []}), 400
    songs = netease_search(q, limit=limit)
    return jsonify({"songs": songs})


@app.route("/api/song/url/netease")
def api_song_url_netease():
    sid = request.args.get("id", "")
    if not sid:
        return jsonify({"url": ""})
    try:
        sid_int = int(sid)
    except (ValueError, TypeError):
        return jsonify({"url": ""})
    url = netease_song_url(sid_int)
    return jsonify({"url": url})


@app.route("/api/lyric/netease")
def api_lyric_netease():
    sid = request.args.get("id", "")
    if not sid:
        return jsonify({"lyric": ""})
    try:
        sid_int = int(sid)
    except (ValueError, TypeError):
        return jsonify({"lyric": ""})
    lrc = netease_lyric(sid_int)
    return jsonify({"lyric": lrc})


# ===== 启动 =====
# ★ 在模块加载时就初始化（兼容 Gunicorn 等 WSGI 服务器）
_initialized = False

def _lazy_init():
    global _initialized
    if not _initialized:
        _initialized = True
        init()
        mode_label = "离线 Demo" if demo_mode else "真实服务"
        print(f"🎵 音乐 AI 伴侣已就绪（{mode_label}）")

_lazy_init()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n🎵 音乐 AI 伴侣已启动 :{port}")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=False)
