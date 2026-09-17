import { useEffect, useRef, useState } from 'react'
import { streamChat, type AgentEvent } from './lib/sse'
import { fetchTools, getSessionId, type ToolInfo } from './lib/api'
import AgentTrace, { type TraceItem } from './components/AgentTrace'
import Player, { type Song } from './components/Player'

interface Turn {
  role: 'user' | 'assistant'
  content: string
  trace: TraceItem[]
}

const EMPTY_TURN: Turn = { role: 'assistant', content: '', trace: [] }

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [session] = useState(() => getSessionId())
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [playing, setPlaying] = useState<Song | null>(null)
  const [now, setNow] = useState<Turn | null>(null)
  const nowRef = useRef<Turn | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  // 流式中的“当前助手回合”用 ref 镜像，避免闭包读到旧值
  const pushNow = (cb: (t: Turn) => Turn) => {
    nowRef.current = cb(nowRef.current ?? { ...EMPTY_TURN })
    setNow({ ...nowRef.current })
  }

  const commitNow = () => {
    // React may run this updater after the streaming ref has been cleared.
    const completed = nowRef.current
    if (completed && completed.content) {
      setTurns((t) => [...t, completed])
    }
    nowRef.current = null
    setNow(null)
    setBusy(false)
  }

  useEffect(() => {
    fetchTools().then(setTools).catch(console.error)
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, now, playing])

  const onEvent = (e: AgentEvent) => {
    switch (e.event) {
      case 'reply_chunk':
        pushNow((t) => ({ ...t, content: t.content + e.data.content }))
        break
      case 'tool_call':
        pushNow((t) => ({
          ...t,
          trace: [...t.trace, { kind: 'call', name: e.data.name, args: e.data.args }],
        }))
        break
      case 'tool_result':
        pushNow((t) => ({
          ...t,
          trace: [...t.trace, { kind: 'result', name: e.data.name, result: e.data.result }],
        }))
        if (e.data.name === 'play_song') {
          const r = e.data.result as Record<string, unknown> & { song?: string; artist?: string; url?: string }
          if (r?.url) setPlaying({ name: r.song ?? '未知', artist: r.artist ?? '', url: r.url })
        }
        break
      case 'done':
        commitNow()
        break
      case 'error':
        pushNow((t) => ({ ...t, content: t.content || '⚠️ 出错了：' + e.data.message }))
        commitNow()
        break
      default:
        break
    }
  }

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    setTurns((t) => [...t, { role: 'user', content: text, trace: [] }])
    nowRef.current = { ...EMPTY_TURN }
    setNow({ ...EMPTY_TURN })
    try {
      await streamChat(text, session, onEvent)
      commitNow()
    } catch (err) {
      pushNow((t) => ({ ...t, content: t.content || `⚠️ 请求失败：${String(err)}` }))
      commitNow()
    }
  }

  const suggestions = [
    '推荐一首适合晚上听的歌',
    '我想听周杰伦的晴天',
    '今天下雨，推荐点应景的歌',
    '我喜欢民谣，推荐几首',
  ]

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>🎵 音乐 AI 伴侣</h1>
        <p className="sub">基于 Function Calling 的音乐 Agent</p>
        <div className="badges">
          <span>Agent</span>
          <span>Function Calling</span>
          <span>SSE 流式</span>
          <span>记忆</span>
        </div>
        <div className="tools-panel">
          <h2>Agent 可用工具（{tools.length}）</h2>
          <ul>
            {tools.map((t) => (
              <li key={t.name}>
                <code>{t.name}</code>
                <span className="tool-desc">{t.description}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="session-hint">
          会话 ID：<code>{session}</code>
        </div>
      </aside>

      <main className="chat">
        <Player song={playing} />

        <div className="turns">
          {turns.map((t, i) => (
            <div key={i} className={`turn ${t.role}`}>
              <div className="bubble">{t.content}</div>
              {t.trace.length > 0 && <AgentTrace trace={t.trace} />}
            </div>
          ))}

          {now && (
            <div className="turn assistant">
              <div className={`bubble ${now.content ? '' : 'thinking'}`}>
                {now.content || '思考中…'}
              </div>
              {now.trace.length > 0 && <AgentTrace trace={now.trace} />}
            </div>
          )}

          {turns.length === 0 && !now && (
            <div className="welcome">
              <p>你好，我是小祥大发 👋</p>
              <p>试着让我帮你找歌、推荐、或者聊聊音乐吧：</p>
              <div className="suggestions">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => setInput(s)} disabled={busy}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="input-bar">
          <input
            value={input}
            placeholder="聊聊音乐，或说想听的歌…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
            disabled={busy}
          />
          <button onClick={send} disabled={busy || !input.trim()}>
            {busy ? '回复中' : '发送'}
          </button>
        </div>
      </main>
    </div>
  )
}
