/**
 * Recurring Upcoming Payment date math.
 *
 * Keep in sync with ``lyqd.cash.recurring`` (Python). Same function names /
 * semantics so calendar + free-cash horizon stay aligned.
 */

export const FREQUENCIES = ['Weekly', 'Monthly', 'Quarterly']

export function parseISODate(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toISODate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function addDaysISO(iso, days) {
  const d = parseISODate(iso)
  d.setDate(d.getDate() + days)
  return toISODate(d)
}

/** Month-end safe advance (matches Frappe ``add_months`` day clamping). */
export function addMonthsISO(iso, months) {
  const d = parseISODate(iso)
  const day = d.getDate()
  d.setDate(1)
  d.setMonth(d.getMonth() + months)
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
  d.setDate(Math.min(day, last))
  return toISODate(d)
}

/** Advance one period from ``due`` — mirrors ``next_due_after``. */
export function nextDueAfter(due, frequency) {
  const freq = String(frequency || 'Monthly').trim()
  if (freq === 'Weekly') return addDaysISO(due, 7)
  if (freq === 'Quarterly') return addMonthsISO(due, 3)
  return addMonthsISO(due, 1)
}

/**
 * Dates from next_due stepping forward while date <= horizon_end (and optional end).
 * ``asOf`` is accepted for API parity with Python (overdue next_due still included).
 */
export function iterOccurrenceDates(
  nextDue,
  frequency,
  asOf,
  horizonEnd,
  recurrenceEnd = null,
) {
  void asOf
  let cursor = parseISODate(nextDue)
  const end = parseISODate(horizonEnd)
  const stop = recurrenceEnd ? parseISODate(recurrenceEnd) : null
  if (stop && cursor > stop) return []
  const out = []
  let guard = 0
  while (cursor <= end && guard < 400) {
    if (stop && cursor > stop) break
    out.push(toISODate(cursor))
    cursor = parseISODate(nextDueAfter(toISODate(cursor), frequency))
    guard += 1
  }
  return out
}

/**
 * Annotate a Planned row with horizon totals — mirrors ``expand_recurring_row``.
 * Mutates and returns ``row``.
 */
export function expandRecurringRow(row, asOf, horizonDays) {
  const period = Number(row?.amount) || 0
  row.period_amount = period
  row.occurrence_count = 1
  row.occurrence_dates = row?.due_date ? [String(row.due_date).slice(0, 10)] : []

  if (!Number(row?.is_recurring)) return row

  let frequency = String(row.frequency || 'Monthly').trim()
  if (!FREQUENCIES.includes(frequency)) frequency = 'Monthly'
  if (!row.due_date) return row

  const horizonEnd = addDaysISO(String(asOf).slice(0, 10), Number(horizonDays) || 0)
  const dates = iterOccurrenceDates(
    String(row.due_date).slice(0, 10),
    frequency,
    String(asOf).slice(0, 10),
    horizonEnd,
    row.recurrence_end ? String(row.recurrence_end).slice(0, 10) : null,
  )
  if (!dates.length) {
    row.amount = 0
    row.occurrence_count = 0
    row.occurrence_dates = []
    return row
  }
  row.occurrence_dates = dates
  row.occurrence_count = dates.length
  row.amount = period * dates.length
  return row
}
