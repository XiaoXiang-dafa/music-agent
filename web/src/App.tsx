import { useEffect, useRef, useState } from 'react'
import Player, { type Song } from './components/Player'
import { getSessionId } from './lib/api'
import { streamChat, type AgentEvent } from './lib/sse'

interface Turn {
  role: 'user' | 'assistant'
  content: string
}

const EMPTY_TURN: Turn = { role: 'assistant', content: '' }

const suggestions = [
  '放一首周杰伦的晴天',
  '推荐一首适合夜晚的歌',
  '聊聊最近循环的音乐',
]

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [session] = useState(() => getSessionId())
  const [playing, setPlaying] = useState<Song | null>(null)
  const [now, setNow] = useState<Turn | null>(null)
  const [lastFailed, setLastFailed] = useState('')
  const nowRef = useRef<Turn | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const pushNow = (cb: (turn: Turn) => Turn) => {
    nowRef.current = cb(nowRef.current ?? { ...EMPTY_TURN })
    setNow({ ...nowRef.current })
  }

  const commitNow = () => {
    // React may run this updater after the streaming ref has been cleared.
    const completed = nowRef.current
    if (completed && completed.content) {
      setTurns((turns) => [...turns, completed])
    }
    nowRef.current = null
    setNow(null)
    setBusy(false)
  }

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns, now, playing])

  const onEvent = (event: AgentEvent) => {
    switch (event.event) {
      case 'reply_chunk':
        pushNow((turn) => ({ ...turn, content: turn.content + event.data.content }))
        break
      case 'tool_result': {
        if (event.data.name !== 'play_song') break
        const result = event.data.result as {
          song?: string
          artist?: string
          url?: string
          cover?: string
          source?: string
        }
        if (result?.url) {
          setPlaying({
            name: result.song ?? '未知歌曲',
            artist: result.artist ?? '',
            url: result.url,
            cover: result.cover ?? '',
            source: result.source ?? '',
          })
        }
        break
      }
      case 'done':
        commitNow()
        break
      case 'error':
        pushNow((turn) => ({
          ...turn,
          content: turn.content || event.data.message || '处理请求时发生错误',
        }))
        commitNow()
        break
      default:
        break
    }
  }

  const send = async (preset?: string) => {
    const text = (preset ?? input).trim()
    if (!text || busy) return

    setInput('')
    setBusy(true)
    setLastFailed('')
    setTurns((turns) => [...turns, { role: 'user', content: text }])
    nowRef.current = { ...EMPTY_TURN }
    setNow({ ...EMPTY_TURN })

    try {
      await streamChat(text, session, onEvent)
      commitNow()
    } catch (error) {
      const message = error instanceof Error ? error.message : '处理请求时发生错误'
      setLastFailed(text)
      pushNow((turn) => ({ ...turn, content: turn.content || message }))
      commitNow()
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="音乐伴侣首页">
          <span className="brand-mark" aria-hidden="true">M</span>
          <span>音乐伴侣</span>
        </a>
        <div className="presence" aria-label="伴侣在线">
          <span className="presence-dot" aria-hidden="true" />
          在你身边
        </div>
      </header>

      <main className="workspace">
        <section className="listening-panel" aria-label="音乐播放器">
          <p className="eyebrow">NOW PLAYING</p>
          <Player song={playing} />
          <div className="listening-note">
            <span>01</span>
            <p>一句话点歌，伴侣会替你寻找可播放的原版音源。</p>
          </div>
        </section>

        <section className="companion-panel" aria-label="音乐伴侣对话">
          <div className="conversation-heading">
            <div>
              <p className="eyebrow">COMPANION</p>
              <h1>今天想听什么？</h1>
            </div>
            <span className={busy ? 'reply-state is-busy' : 'reply-state'}>
              {busy ? '正在找音乐' : '随时可以聊'}
            </span>
          </div>

          <div className="turns" aria-live="polite" aria-busy={busy}>
            {turns.length === 0 && !now && (
              <div className="welcome">
                <p className="welcome-lead">我是你的音乐伴侣。</p>
                <p>告诉我歌名、歌手，或者你此刻的心情。</p>
                <div className="suggestions" aria-label="快捷提问">
                  {suggestions.map((suggestion, index) => (
                    <button key={suggestion} onClick={() => void send(suggestion)} disabled={busy}>
                      <span>0{index + 1}</span>
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn, index) => (
              <div key={`${turn.role}-${index}`} className={`turn ${turn.role}`}>
                <span className="turn-label">{turn.role === 'user' ? '你' : '伴侣'}</span>
                <div className="bubble">{turn.content}</div>
              </div>
            ))}

            {now && (
              <div className="turn assistant">
                <span className="turn-label">伴侣</span>
                <div className={now.content ? 'bubble' : 'bubble thinking'}>
                  {now.content || (
                    <span className="thinking-dots" aria-label="正在思考">
                      <i /><i /><i />
                    </span>
                  )}
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {lastFailed && !busy && (
            <button className="retry" onClick={() => void send(lastFailed)}>
              刚才没接上，点这里重试
            </button>
          )}

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault()
              void send()
            }}
          >
            <label className="sr-only" htmlFor="message">给音乐伴侣发消息</label>
            <input
              id="message"
              value={input}
              placeholder="点歌，或者聊聊音乐…"
              onChange={(event) => setInput(event.target.value)}
              disabled={busy}
              autoComplete="off"
            />
            <button type="submit" disabled={busy || !input.trim()} aria-label="发送消息">
              <span>发送</span>
              <b aria-hidden="true">↗</b>
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}
