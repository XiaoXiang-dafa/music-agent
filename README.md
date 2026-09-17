# 个性化音乐 AI 伴侣

一个基于 Function Calling 的音乐智能体。用自然语言说「找歌、点歌、要推荐」，它会调用音乐工具，结合长期记忆和天气、时段信息，自己完成理解意图、检索曲库、推荐、播放这一整条链路，而不是拿文本标签硬匹配。

项目带两个前端：React + Vite 的网页演示，通过 SSE 流式展示推理和工具调用过程；还有一个微信小程序。

工具定义、注册和执行事件来自仓库内置的 `packages/agent-core`，音乐工具、长期记忆、Prompt、Flask API 和前端都在本项目里。克隆一个仓库就能装、能跑。

## 功能

- Function Calling Agent：工具注册表加 ReAct 执行循环，LLM 负责决策，音乐能力是它可以调用的工具，替代了原先从文本里抠 `[[PLAY:…]]` 的约定。
- 9 个音乐工具：`search_songs`、`get_song_url`、`get_lyrics`、`get_daily_recommendation`、`get_weather`、`play_song`、`save_favorite`、`remember_taste`、`get_user_profile`。新工具实现一个函数就能接入。
- 长期记忆：SQLite 持久化，主动收藏、播放历史、口味画像分开存，避免把播放过误判成喜欢。
- SSE 和 Trace：回复逐 token 下发，每次请求生成 `trace_id`，记录工具状态、耗时、音源回退和运行统计。
- 多步推理：可以先查天气、再看用户画像、再搜歌、最后播放；发现返回的不是原唱会重新检索。
- 双音源：QQ 音乐和网易云统一接口，可切换，播放地址拿不到时自动回退。

## 目录结构

```
app.py                   Flask 入口
agent/
  registry.py            工具注册表
  loop.py                Function Calling 执行循环
  prompts.py             system prompt 组装
tools/
  music.py               搜索、播放地址、歌词、推荐
  weather.py             天气
  playback.py            定位歌曲、触发播放、音源回退
  memory.py              SQLite 记忆和记忆工具
modules/                 底层音源
packages/agent-core/     通用 Function Calling 运行时
web/                     React + Vite + TS 前端
  src/lib/sse.ts         SSE 帧解析
  src/components/        AgentTrace、Player
  src/App.tsx            聊天界面、工具目录、播放器
miniapp/                 微信小程序
```

`bot.py`、`cli.py`、`demo.py` 等旧入口也保留着，作为底层音源和产品壳复用。

## 一次请求的流程

用户消息进来后先拼 system prompt，LLM 决定直接回复还是调用工具；工具执行完把结果回填给 LLM 继续推理，直到产出纯文本回复。整个过程通过 SSE 下发回复和工具事件。

## 快速开始

```bash
git clone https://github.com/XiaoXiang-dafa/music-agent.git
cd music-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 通过 `-e ./packages/agent-core` 安装仓库内置的运行时，不依赖其他本地仓库。

环境变量：

| 变量 | 说明 | 必填 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 是 |
| `QQMUSIC_COOKIE` | QQ 音乐 Cookie，播放地址需要，可能过期 | 否 |
| `WEATHER_API_KEY` | 和风天气 Key | 否 |
| `DEMO_MODE` | 设为 `1` 时使用离线演示模型和曲库 | 否 |

`config.json` 和 `config.example.json` 只保留占位符，凭据走环境变量，不要把 Cookie、API Key 或 Token 写回配置文件：

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

DEEPSEEK_API_KEY="sk-..." python3 app.py
# 浏览器打开 http://127.0.0.1:5050
```

没有 API Key 可以直接启动离线 Demo：

```bash
cd web && npm ci && npm run build && cd ..
DEMO_MODE=1 python3 app.py
```

Demo 模式不访问 DeepSeek、QQ 音乐或网易云，但 Agent 循环、Function Calling、工具注册、长期记忆和 SSE 都是真实链路。播放器收到的是运行时生成的短提示音，只用来验证编排和播放闭环，不代表真实歌曲。

### 验证

```bash
DEMO_MODE=1 python3 -m pytest -q
PYTHONPATH=packages/agent-core/src python3 -m pytest packages/agent-core/tests -q

cd web
npm ci
node --test tests/*.test.mjs
npm run build
```

### 安全边界

- 仓库里没有 API Key、Cookie、聊天记录、SQLite 数据库或私有部署配置。
- 封面取色接口只允许 QQ 音乐和网易云的 HTTPS 图片域名，并限制下载和像素大小。
- 聊天接口有请求体、消息、会话 ID 校验和单进程限流。正式多实例部署时，还需要在网关层加鉴权和分布式限流。
- 开发服务默认只监听 `127.0.0.1`，不要把带真实密钥的进程直接暴露到公网。

### 前端开发

```bash
cd web
npm install            # 或用 --cache 规避 npm cache 权限问题
npm run dev            # http://127.0.0.1:5173，/api 代理到 5050
```

日常使用直接打开 Flask 的 `http://127.0.0.1:5050`，只有开发前端时才用 `http://127.0.0.1:5173`。发「放一首周杰伦的晴天」就能验证流式回复和播放器。

### 微信小程序

用微信开发者工具打开 `miniapp/` 或项目根目录，`project.config.json` 已配好 `miniprogramRoot`，`miniapp/app.js` 里的 `apiBase` 指向后端。

## 工具一览

通过 `/api/tools` 动态获取。

| 工具 | 作用 |
|------|------|
| `search_songs(keyword, source)` | 在 QQ/网易云搜歌 |
| `get_song_url(song_id, source)` | 获取播放地址 |
| `get_lyrics(song_id, source)` | 获取歌词 |
| `get_daily_recommendation()` | 结合天气、时段、口味生成今日歌单 |
| `get_weather()` | 查天气 |
| `play_song(song_name, artist)` | 定位歌曲并播放 |
| `save_favorite(song, artist)` | 收藏到长期记忆 |
| `remember_taste(taste)` | 记住音乐偏好 |
| `get_user_profile()` | 读取画像、收藏、口味 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat/stream` | SSE 流式对话 |
| `POST` | `/api/chat` | 非流式对话，兼容小程序 |
| `GET` | `/api/tools` | 可用工具列表 |
| `GET` | `/api/traces?limit=20` | 最近 1～100 次运行记录 |
| `GET` | `/api/traces/<trace_id>` | 单次运行详情 |
| `GET` | `/api/morning` / `/api/music` | 早安消息、今日歌单 |
| `GET` | `/api/search` / `/api/song/url` / `/api/lyric` | 音源接口 |
| `GET` | `/api/cover/color` | 封面主色 |

Demo 模式下，SSE 的 `start`、`tool_call`、`tool_result`、`done` 共享同一个 `trace_id`，工具事件带 `call_id`，结果事件带 `status` 和 `duration_ms`。Trace 存在 `data/traces.db`，长期记忆存在 `data/memory.db`。

Trace 只记录运行状态和工具元数据，不保存用户消息、System Prompt、完整工具结果、播放地址、歌词、密钥或 Cookie。这是本地轻量可观测性，不替代分布式监控。

## 设计取舍

1. Function Calling 而不是文本标签：`[[PLAY:…]]` 依赖输出格式约定，解析脆弱；Function Calling 让 LLM 用类型化参数调用工具，结果可校验、可追溯。
2. Agent 循环：`max_steps` 限制推理轮数，工具结果以 `role:tool` 回填，LLM 可以自我纠正，发现翻唱就重新检索。
3. 记忆注入：主动收藏、最近播放、口味摘要分开拼进 system prompt，播放只写历史，明确收藏才写 favorites。
4. 音源抽象：`search_songs` 和 `get_song_url` 统一接口加 `source` 参数，拿不到地址就回退另一音源。
5. 事件循环复用：`modules/qqmusic.py` 用后台常驻事件循环，避免每次 `asyncio.run` 新建、销毁循环带来的性能和崩溃问题。
