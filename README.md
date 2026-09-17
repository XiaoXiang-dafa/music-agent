# 个性化音乐 AI 伴侣 Agent

> 一个基于 **Function Calling** 的个性化音乐智能体（Agent）。
> 用户用自然语言「找歌、点歌、要推荐」，Agent 自动调用音乐域工具、结合**长期记忆**与**天气/时段推理**，
> 自主完成 _理解意图 → 检索曲库 → 个性化推荐 → 真实播放_ 的完整链路，而不是简单匹配文本标签。

同时提供 **两个前端**：一个 React + Vite 的 **Web 演示端**（SSE 流式展示 Agent 推理与工具调用）、一个 **微信小程序**。

本项目的工具定义、注册和执行事件由仓库内置的 **`packages/agent-core 0.1.0`** 提供；音乐工具、长期记忆、Prompt、Flask API 和前端仍由本项目负责。克隆一个仓库即可安装与运行。

---

## ✨ 核心亮点

- **真正的 Function Calling Agent**：自研工具注册表 + ReAct 执行循环，替代原先「从文本抠 `[[PLAY:…]]`」的模板约定。LLM 是决策者，音乐能力是它可调用的工具。
- **9 个音乐域工具**：`search_songs` / `get_song_url` / `get_lyrics` / `get_daily_recommendation` / `get_weather` / `play_song` / `save_favorite` / `remember_taste` / `get_user_profile`，新工具实现一个函数即可热插拔。
- **长期记忆 + 个性化**：SQLite 会话隔离持久化，主动收藏、播放历史与口味画像分别存储并注入 Prompt，避免把“播放过”误判成“喜欢”。
- **SSE + Trace**：逐 token 下发回复及工具事件；每次请求生成 `trace_id`，记录工具状态、耗时、音源回退与运行统计。
- **多步推理 & 自纠错**：Agent 可先查天气、再查用户画像、再搜索歌曲、最后播放；发现返回不是原唱时会重新检索（有真实验证）。
- **双音源**：QQ 音乐 + 网易云统一抽象，音源可热切换，播放地址自动回退。

---

## 🏗️ 架构

```
app.py                     # Flask 入口（路由薄，只做 HTTP + 组装上下文）
├─ agent/                  # Agent 核心（无 IO 依赖，纯逻辑）
│   ├─ registry.py         #   工具注册表（可热插拔）
│   ├─ loop.py             #   Function Calling 执行循环（流式/非流式）
│   └─ prompts.py          #   system prompt 组装（人设 + 工具说明 + 记忆）
├─ tools/                  # 音乐域工具（每个 = 一个可被 LLM 调用的函数）
│   ├─ music.py            #   搜索 / 播放地址 / 歌词 / 个性化推荐
│   ├─ weather.py          #   天气（场景化推荐用）
│   ├─ playback.py         #   play_song（定位歌曲 + 触发真实播放 + 音源回退）
│   └─ memory.py           #   SQLite 记忆（收藏/偏好/画像）+ 记忆工具
├─ modules/                # 底层音源与既有能力（qqmusic / netease / weather / music…）
├─ packages/agent-core/   # 内置的通用 Function Calling 运行时
├─ web/                    # React + Vite + TS 演示前端（SSE 流式）
│   └─ src/
│       ├─ lib/sse.ts      #   fetch + ReadableStream 解析 SSE 帧
│       ├─ components/     #   AgentTrace（工具轨迹）/ Player（音频）
│       └─ App.tsx         #   聊天 UI + Agent 工具目录 + 播放器
└─ miniapp/                # 微信小程序前端（沿用既有产品壳）
```

**Agent 一次请求的数据流**：

```
用户消息 ──→ build_system_prompt(人设 + 记忆 + 工具说明)
                 │
                 ▼
        stream_agent(推理循环)
           │  ① LLM 决策：文本回复 或 tool_calls
           ▼
        ② 执行工具 → 得到结果          ──(SSE: tool_call / tool_result)
           ▼
        ③ 把结果喂回 LLM，继续推理      ──(SSE: reply_chunk 逐 token)
           ▼
        ④ 收到纯文本回复 → 结束          (SSE: done)
```

---

## 🚀 快速开始

### 依赖
```bash
git clone https://github.com/XiaoXiang-dafa/music-agent.git
cd music-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 会通过 `-e ./packages/agent-core` 安装仓库内置的公共运行时，不依赖其他本地仓库。

### 环境变量
| 变量 | 说明 | 必填 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek（OpenAI 兼容）API Key | ✅ |
| `QQMUSIC_COOKIE` | QQ 音乐登录 Cookie（播放地址用，可选/可过期） | 否 |
| `WEATHER_API_KEY` | 和风天气 Key（天气/场景推荐用） | 否 |
| `DEMO_MODE` | 设为 `1` 时使用完全离线的演示模型与曲库 | 否 |

仓库中的 `config.json` 和 `config.example.json` 只保留脱敏占位符。请通过环境变量注入凭据，不要把 Cookie、API Key 或 Token 写回配置文件：

```bash
export DEEPSEEK_API_KEY="sk-..."
export QQMUSIC_COOKIE="..."        # 可选，播放功能需要
export WEATHER_API_KEY="..."        # 可选，天气功能需要
python3 app.py
```

### 本地启动
```bash
cd web
npm ci
npm run build
cd ..

# 使用真实服务
DEEPSEEK_API_KEY="sk-..." python3 app.py
# 浏览器打开 http://127.0.0.1:5050
```

没有 API Key 时可直接启动离线 Demo：

```bash
cd web && npm ci && npm run build && cd ..
DEMO_MODE=1 python3 app.py
```

Demo 模式不访问 DeepSeek、QQ 音乐或网易云，但仍会执行真实的 Agent 循环、Function Calling、Tool Registry、长期记忆和 SSE 链路。播放器收到的是运行时生成的短提示音，仅用于验证编排与播放闭环，不代表真实歌曲内容。

### 快速验证

```bash
# Python 应用 + 内置 agent-core
DEMO_MODE=1 python3 -m pytest -q
PYTHONPATH=packages/agent-core/src python3 -m pytest packages/agent-core/tests -q

# React 回归与生产构建
cd web
npm ci
node --test tests/*.test.mjs
npm run build
```

### 安全边界

- 仓库不包含 API Key、Cookie、私人聊天记录、SQLite 数据库或部署私有配置。
- 封面取色接口仅允许 QQ 音乐/网易云的 HTTPS 图片域名，并限制下载与像素大小。
- 聊天接口有请求体、消息、会话 ID 校验和单进程限流；若要正式多实例部署，仍应在网关层增加鉴权与分布式限流。
- 开发服务默认只监听 `127.0.0.1`；不要将带真实密钥的本地进程直接暴露到公网。

### 前端开发模式
```bash
cd web
npm install            # 或用 --cache 规避 npm cache 权限问题
npm run dev            # http://127.0.0.1:5173 （/api 已代理到 5050）
```

日常使用直接打开 Flask 的 `http://127.0.0.1:5050`。只有开发前端时才需要访问 `http://127.0.0.1:5173`。发「放一首周杰伦的晴天」即可验证流式回复与原生播放器闭环。

### 微信小程序
用微信开发者工具打开 `miniapp/`（或项目根，`project.config.json` 已配 `miniprogramRoot`）。`miniapp/app.js` 里 `apiBase` 指向后端。

---

## 🧰 Agent 工具一览（通过 `/api/tools` 动态获取）

| 工具 | 作用 |
|------|------|
| `search_songs(keyword, source)` | 在 QQ/网易云曲库搜索歌曲 |
| `get_song_url(song_id, source)` | 获取可播放地址 |
| `get_lyrics(song_id, source)` | 获取歌词 |
| `get_daily_recommendation()` | 结合天气/时段/口味生成今日歌单 |
| `get_weather()` | 查询天气（场景化推荐） |
| `play_song(song_name, artist)` | 定位歌曲并触发真实播放 |
| `save_favorite(song, artist)` | 保存收藏到长期记忆 |
| `remember_taste(taste)` | 记住用户音乐偏好 |
| `get_user_profile()` | 读取用户画像/收藏/口味 |

---

## 📡 API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat/stream` | **SSE 流式 Agent 对话**（`start`/`tool_call`/`tool_result`/`reply_chunk`/`done`） |
| `POST` | `/api/chat` | 非流式 Agent 对话（返回 `reply`/`steps`/`tool_calls`/`play`，兼容小程序） |
| `GET` | `/api/tools` | 列出 Agent 可用工具 |
| `GET` | `/api/traces?limit=20` | 最近 1～100 次 Agent 运行及当前窗口统计 |
| `GET` | `/api/traces/<trace_id>` | 单次运行与脱敏工具事件详情 |
| `GET` | `/api/morning` / `/api/music` | 早安消息 / 今日歌单 |
| `GET` | `/api/search` / `/api/song/url` / `/api/lyric` | 音源接口（QQ/网易云各一组） |
| `GET` | `/api/cover/color` | 封面主色提取（播放器背景） |

Demo 模式下，SSE 的 `start/tool_call/tool_result/done` 共享同一个 `trace_id`；工具事件还包含 `call_id`，结果事件包含 `status` 和 `duration_ms`。Trace 保存在 `data/traces.db`，长期记忆保存在 `data/memory.db`。

隐私边界：Trace 只落库运行状态和工具元数据，不保存用户消息、System Prompt、完整工具结果、播放 URL/Data URL、歌词、密钥或 Cookie。该能力是本地轻量可观测性，不代表分布式监控或线上 SLA。

---

## 🧠 设计取舍（面试可讲）

1. **为什么用 Function Calling 而不是文本标签**：`[[PLAY:…]]` 依赖 LLM 输出格式约定，解析脆弱、无法表达复杂意图；Function Calling 让 LLM 以类型化参数显式调用工具，结果可校验、可追溯、可扩展。
2. **Agent 循环**：`max_steps` 限制推理轮数，避免死循环；工具调用结果以 `role:tool` 回填，LLM 可依据结果自我纠正（如发现翻唱就重新检索）。
3. **记忆注入**：把用户主动收藏、最近播放与口味摘要分别拼进 system prompt；播放仅写历史，只有明确收藏意图才写 favorites。
4. **音源抽象**：`search_songs/get_song_url` 统一接口 + `source` 参数，QQ/网易云可切换；播放地址拿不到时自动回退另一音源。
5. **事件循环复用**：`modules/qqmusic.py` 用后台常驻事件循环 + `asyncio.run_coroutine_threadsafe`，避免每次调用 `asyncio.run` 新建/销毁循环导致的性能与崩溃问题。

---

## 📁 目录结构（新建部分）
```
agent/           # Agent 核心（registry/loop/prompts）
tools/           # 音乐域工具 + 记忆存储
web/             # React+Vite+TS 演示前端
```

> 原有 `modules/`、`miniapp/`、`bot.py`、`cli.py` 等保留，作为底层音源与既有产品壳复用。
