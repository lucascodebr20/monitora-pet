import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/lib/eventActivity.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext },
})
const { activityEvents } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('a pet present without using food, water or litter never increases its activity totals', () => {
  const events = ['FOOD', 'WATER', 'LITTER'].flatMap(zone_type => [
    { id: `${zone_type}-used`, pet_id: 'cat', zone_type, review_decision: 'CONFIRMED' },
    { id: `${zone_type}-unused`, pet_id: 'cat', zone_type, review_decision: 'NO_ACTION' },
    { id: `${zone_type}-rejected`, pet_id: null, zone_type, review_decision: 'FALSE_POSITIVE' },
  ])
  events.push({ id: 'other-cat', pet_id: 'other', zone_type: 'FOOD', review_decision: 'CONFIRMED' })
  const selected = activityEvents(events, 'cat')
  assert.equal(selected.length, 3)
  for (const type of ['FOOD', 'WATER', 'LITTER']) {
    assert.equal(selected.filter(event => event.zone_type === type).length, 1)
  }
  assert.equal(activityEvents(events).length, 4)
  assert.equal(events.length, 10, 'the original history stays intact')
})

test('pending and corrected visits remain visible and corrected zones are counted', () => {
  const events = [
    { id: 'pending', pet_id: 'cat', zone_type: 'WATER', review_decision: null },
    { id: 'corrected', pet_id: 'cat', zone_type: 'FOOD', review_decision: 'CORRECTED' },
    { id: 'not-used', pet_id: 'cat', zone_type: 'FOOD', review_decision: 'NO_ACTION' },
  ]
  assert.deepEqual(
    activityEvents(events, 'cat').map(event => event.id),
    ['pending', 'corrected'],
  )
})
