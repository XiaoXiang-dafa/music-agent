import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { test } from 'node:test'

// Execute the actual callback with React-style deferred functional updates.
const source = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const file = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
let callback
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(file) === 'commitNow') {
    callback = node.initializer.getText(file)
  }
  ts.forEachChild(node, visit)
}
visit(file)
assert.ok(callback)
const javascript = ts.transpileModule(`const commitNow = ${callback}; commitNow();`, {
  compilerOptions: { target: ts.ScriptTarget.ES2020 },
}).outputText

test('completed reply survives clearing ref and repeated completion', () => {
  const completed = { role: 'assistant', content: 'hello', trace: [] }
  const updates = []
  const context = vm.createContext({
    nowRef: { current: completed },
    setTurns: update => updates.push(update),
    setNow: () => {},
    setBusy: () => {},
  })
  vm.runInContext(javascript, context)
  assert.equal(context.nowRef.current, null)
  const turns = updates.reduce((previous, update) => update(previous), [])
  assert.equal(turns.length, 1)
  assert.equal(turns[0], completed)
  vm.runInContext('commitNow()', context)
  assert.equal(updates.length, 1)
})
