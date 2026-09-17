export type AgentEvent =
  | { event: 'start'; data: { session: string; character: string; trace_id?: string; mode?: string } }
  | { event: 'reply_chunk'; data: { content: string } }
  | { event: 'tool_call'; data: { name: string; args: Record<string, unknown>; trace_id?: string; call_id?: string } }
  | { event: 'tool_result'; data: { name: string; result: unknown; trace_id?: string; call_id?: string; status?: string; duration_ms?: number } }
  | { event: 'done'; data: { reply: string; steps: number; truncated?: boolean; trace_id?: string; status?: string; duration_ms?: number } }
  | { event: 'error'; data: { message: string; trace_id?: string } }

function parseFrame(frame: string): AgentEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return null
  let data: unknown = dataLines.join('\n')
  try {
    data = JSON.parse(dataLines.join('\n'))
  } catch {
    /* keep raw */
  }
  return { event, data } as AgentEvent
}

/**
 * 通过 fetch + ReadableStream 消费后端的 SSE 流（POST /api/chat/stream）。
 * 逐帧解析 event:/data:，并把每个事件回调给 onEvent。
 */
export async function streamChat(
  message: string,
  session: string,
  onEvent: (e: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const controller = new AbortController()
  let timedOut = false
  const timeout = window.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, 60_000)
  const forwardAbort = () => controller.abort()
  signal?.addEventListener('abort', forwardAbort, { once: true })

  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message, session }),
      signal: controller.signal,
    })
    if (!resp.ok) {
      throw new Error(resp.status === 429 ? '请求太频繁，请稍后再试' : '处理请求时发生错误')
    }
    if (!resp.headers.get('content-type')?.includes('text/event-stream') || !resp.body) {
      throw new Error('服务返回异常，请稍后重试')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let terminalEventSeen = false

    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        const parsed = parseFrame(frame)
        if (parsed) {
          if (parsed.event === 'done' || parsed.event === 'error') terminalEventSeen = true
          onEvent(parsed)
        }
      }
    }

    if (!terminalEventSeen) throw new Error('连接提前断开，请重试')
  } catch (error) {
    if (timedOut) throw new Error('请求超时，请重试')
    if (signal?.aborted) throw new Error('请求已取消')
    if (error instanceof Error) throw error
    throw new Error('处理请求时发生错误')
  } finally {
    window.clearTimeout(timeout)
    signal?.removeEventListener('abort', forwardAbort)
  }
}
