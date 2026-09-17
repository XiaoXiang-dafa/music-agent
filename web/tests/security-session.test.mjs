import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

test('session ids use cryptographic randomness', () => {
  const source = readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8')

  assert.match(source, /crypto\.randomUUID\(\)/)
  assert.doesNotMatch(source, /Math\.random\(\)/)
})
