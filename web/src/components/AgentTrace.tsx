export interface TraceItem {
  kind: 'call' | 'result'
  name: string
  args?: Record<string, unknown>
  result?: unknown
}

/** 工具调用轨迹：直观展示 Agent 每一步调了哪个工具、返回了什么。 */
export default function AgentTrace({ trace }: { trace: TraceItem[] }) {
  return (
    <div className="trace">
      {trace.map((t, i) => (
        <div className={`trace-item ${t.kind}`} key={i}>
          <span className="trace-kind">{t.kind === 'call' ? '⚙️ 调用' : '📥 返回'}</span>
          <span className="trace-name">{t.name}</span>
          {t.kind === 'call' && t.args && (
            <code className="trace-args">{JSON.stringify(t.args)}</code>
          )}
          {t.kind === 'result' && t.result != null && (
            <code className="trace-args">{summary(resultToText(t.result))}</code>
          )}
        </div>
      ))}
    </div>
  )
}

function resultToText(value: unknown): string {
  if (typeof value === 'string') return value
  if (!value || typeof value !== 'object') return String(value)
  const r = value as Record<string, unknown>
  if (typeof r.error === 'string') return r.error
  if (typeof r.songs !== 'undefined') {
    const list = r.songs as Array<{ name?: string; artist?: string }>
    return `命中 ${list.length} 首: ` + list.slice(0, 3).map((s) => `${s.name ?? ''}-${s.artist ?? ''}`).join(' / ')
  }
  if (typeof r.url === 'string' && r.url) return `可播放地址已拿到`
  return JSON.stringify(r)
}

function summary(s: string, n = 90): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}
