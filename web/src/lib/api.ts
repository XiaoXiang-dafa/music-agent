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
