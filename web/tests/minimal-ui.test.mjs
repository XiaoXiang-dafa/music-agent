import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/index.css', import.meta.url), 'utf8')
const sse = readFileSync(new URL('../src/lib/sse.ts', import.meta.url), 'utf8')

test('main UI only exposes music playback and companion chat', () => {
  assert.doesNotMatch(app, /fetchTools|AgentTrace|tools-panel|session-hint/)
  assert.doesNotMatch(app, /天气|早安|今日歌单|切换角色|新建角色/)
  assert.match(app, /音乐伴侣/)
  assert.match(app, /Player/)
})

test('streaming requests have a timeout and useful failures', () => {
  assert.match(sse, /AbortController/)
  assert.match(sse, /timeout/i)
  assert.match(sse, /处理请求时发生错误|请求超时/)
})

test('layout has responsive mobile treatment and visible focus states', () => {
  assert.match(css, /@media\s*\(max-width:/)
  assert.match(css, /:focus-visible/)
  assert.match(css, /prefers-reduced-motion/)
})
