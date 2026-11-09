/**
 * Parity checks vs ``lyqd.cash.test_recurring`` / ``lyqd.cash.recurring``.
 * Run: node --input-type=module src/utils/recurrence.parity.test.js
 */
import {
  expandRecurringRow,
  iterOccurrenceDates,
  nextDueAfter,
} from './recurrence.js'

function assertEqual(actual, expected, label) {
  const a = JSON.stringify(actual)
  const e = JSON.stringify(expected)
  if (a !== e) {
    console.error(`FAIL ${label}\n  expected ${e}\n  actual   ${a}`)
    process.exitCode = 1
  } else {
    console.log(`ok ${label}`)
  }
}

assertEqual(nextDueAfter('2026-01-15', 'Weekly'), '2026-01-22', 'weekly')
assertEqual(nextDueAfter('2026-01-15', 'Monthly'), '2026-02-15', 'monthly')
assertEqual(nextDueAfter('2026-01-15', 'Quarterly'), '2026-04-15', 'quarterly')

assertEqual(
  iterOccurrenceDates('2026-02-15', 'Monthly', '2026-03-01', '2026-04-30'),
  ['2026-02-15', '2026-03-15', '2026-04-15'],
  'iter includes overdue next due',
)

assertEqual(
  iterOccurrenceDates(
    '2026-01-01',
    'Monthly',
    '2026-01-01',
    '2026-06-30',
    '2026-03-01',
  ),
  ['2026-01-01', '2026-02-01', '2026-03-01'],
  'iter respects recurrence_end',
)

const row = {
  amount: 10_000,
  due_date: '2026-01-01',
  is_recurring: 1,
  frequency: 'Monthly',
}
expandRecurringRow(row, '2026-01-01', 75)
assertEqual(row.period_amount, 10_000, 'period_amount')
if (!(row.occurrence_count >= 2)) {
  console.error('FAIL occurrence_count >= 2', row.occurrence_count)
  process.exitCode = 1
} else {
  console.log('ok occurrence_count >= 2')
}
assertEqual(row.amount, 10_000 * row.occurrence_count, 'horizon amount')

const plain = { amount: 5_000, due_date: '2026-01-01', is_recurring: 0 }
expandRecurringRow(plain, '2026-01-01', 30)
assertEqual(plain.amount, 5_000, 'non-recurring amount')
assertEqual(plain.occurrence_count, 1, 'non-recurring count')

if (!process.exitCode) console.log('All recurrence parity checks passed.')
