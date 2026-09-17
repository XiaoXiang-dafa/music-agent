export interface ToolInfo {
  name: string
  description: string
  parameters: Record<string, { type?: string; description?: string }>
}

export async function fetchTools(): Promise<ToolInfo[]> {
  const resp = await fetch('/api/tools')
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const data = await resp.json()
  return data.tools ?? []
}

/** 生成/读取本地会话 id，用于后端按用户隔离长期记忆。 */
export function getSessionId(): string {
  const key = 'music_agent_session'
  let sid = localStorage.getItem(key)
  if (!sid) {
    sid = 'u_' + crypto.randomUUID()
    localStorage.setItem(key, sid)
  }
  return sid
}
