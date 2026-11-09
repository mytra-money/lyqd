/**
 * Map LYQD plan rows → frappe-ui Calendar events (full-day by due date).
 * Recurring series expand via ``recurrence.js`` (parity with ``lyqd.cash.recurring``).
 */

import {
  addMonthsISO,
  iterOccurrenceDates,
  toISODate,
} from '@/utils/recurrence'

const CALENDAR_HORIZON_MONTHS = 18

function cashEffectOf(row) {
  const ce = row?.cash_effect || 'Outflow'
  return ce === 'Setoff' ? 'Inflow' : ce
}

function eventColor(row) {
  return cashEffectOf(row) === 'Inflow' ? 'green' : 'orange'
}

function eventId(row) {
  if (row?._schedule && row.split_name) {
    return `split:${row.parent_payment || ''}:${row.split_name}`
  }
  return String(row?.name || '')
}

function calendarHorizonEnd(asOf) {
  return addMonthsISO(asOf, CALENDAR_HORIZON_MONTHS)
}

function todayISO() {
  return toISODate(new Date())
}

/** Per-cycle amount — free-cash expand replaces ``amount`` with horizon total. */
function periodAmount(row) {
  if (row?.period_amount != null && row.period_amount !== '') {
    return Number(row.period_amount) || 0
  }
  const count = Number(row?.occurrence_count) || 0
  if (row?.is_recurring && count > 1) {
    return (Number(row.amount) || 0) / count
  }
  return Number(row?.amount) || 0
}

function datesForCalendarRow(row, asOf, horizonEnd) {
  if (!row?.due_date) return []
  const nextDue = String(row.due_date).slice(0, 10)
  if (!row.is_recurring) return [nextDue]
  return iterOccurrenceDates(
    nextDue,
    row.frequency || 'Monthly',
    asOf,
    horizonEnd,
    row.recurrence_end ? String(row.recurrence_end).slice(0, 10) : null,
  )
}

/** Flatten nested / split plan roots into calendar-ready leaf rows with due dates. */
function flattenPlanForCalendar(nestedRoots) {
  const out = []
  for (const root of nestedRoots || []) {
    const kids = root._children || []
    const scheduleKids = kids.filter((c) => c._schedule)
    if (scheduleKids.length) {
      for (const c of scheduleKids) {
        if (!c.due_date) continue
        out.push({
          ...c,
          parent_payment: root.name,
          cash_effect: root.cash_effect || c.cash_effect,
          category: root.category || c.category,
          source_doctype: root.source_doctype,
          source_name: root.source_name,
        })
      }
      continue
    }
    if (kids.length) {
      // Nest: one event on the parent — due date cascades to children
      if (root.due_date) out.push(root)
      continue
    }
    if (root.due_date) out.push(root)
  }
  return out
}

/** Parse ``baseId@YYYY-MM-DD`` calendar event ids (recurring + one-shot). */
export function parseCalendarEventId(eventIdValue) {
  const id = String(eventIdValue || '')
  const at = id.lastIndexOf('@')
  if (at > 0 && /^\d{4}-\d{2}-\d{2}$/.test(id.slice(at + 1))) {
    return { baseId: id.slice(0, at), occurrenceDate: id.slice(at + 1) }
  }
  return { baseId: id, occurrenceDate: null }
}

export function planRowsToCalendarEvents(nestedRoots, opts = {}) {
  const asOf = opts.asOf || todayISO()
  const horizonEnd = opts.horizonEnd || calendarHorizonEnd(asOf)
  const events = []
  for (const row of flattenPlanForCalendar(nestedRoots)) {
    const dates = datesForCalendarRow(row, asOf, horizonEnd)
    const amount = periodAmount(row)
    const base = eventId(row)
    for (const due of dates) {
      events.push({
        id: `${base}@${due}`,
        title: row.title || row.name,
        fromDate: due,
        toDate: due,
        fromTime: '00:00:00',
        toTime: '23:59:59',
        isFullDay: true,
        color: eventColor(row),
        _planName: row.name,
        _splitName: row.split_name || '',
        _parentPayment: row.parent_payment || '',
        _isSchedule: Boolean(row._schedule),
        _isNestChild: Boolean(row.parent_payment && !row._schedule),
        _isRecurring: Boolean(row.is_recurring),
        _frequency: row.frequency || '',
        _occurrenceDate: due,
        _isSeriesAnchor: due === String(row.due_date || '').slice(0, 10),
        _amount: amount,
        _cashEffect: cashEffectOf(row),
        _category: row.category || '',
        _status: row.status || 'Planned',
      })
    }
  }
  return events
}

export function findPlanRowForEvent(nestedRoots, eventIdValue) {
  const flat = flattenPlanForCalendar(nestedRoots)
  const { baseId } = parseCalendarEventId(eventIdValue)
  if (baseId.startsWith('split:')) {
    const parts = baseId.split(':')
    const splitName = parts.slice(2).join(':')
    return flat.find((r) => r._schedule && r.split_name === splitName) || null
  }
  return flat.find((r) => !r._schedule && r.name === baseId) || null
}

/** Detail lines for the calendar event popover (list-style info). */
export function calendarEventDetailLines(calendarEvent, nestedRoots, asOf, formatters) {
  const { formatDate, formatINR, commitmentDetailLines } = formatters
  const ev = calendarEvent?.value ?? calendarEvent
  if (!ev) return []
  const row = findPlanRowForEvent(nestedRoots, ev.id)
  const occ = String(ev.fromDate || ev._occurrenceDate || '').slice(0, 10)
  if (!row) {
    const lines = []
    if (occ) lines.push({ label: 'Due', value: formatDate(occ) })
    if (ev._amount != null) lines.push({ label: 'Amount', value: formatINR(ev._amount) })
    if (ev._cashEffect) lines.push({ label: 'Effect', value: ev._cashEffect })
    if (ev._category) lines.push({ label: 'Category', value: ev._category })
    if (ev._status) lines.push({ label: 'Status', value: ev._status })
    if (ev._isRecurring) {
      lines.push({ label: 'Repeats', value: ev._frequency || 'Monthly' })
    }
    return lines
  }
  const proxy = {
    ...row,
    due_date: occ || row.due_date,
    amount: ev._amount != null ? ev._amount : row.amount,
    period_amount:
      row.period_amount != null
        ? row.period_amount
        : ev._amount != null
          ? ev._amount
          : row.amount,
    occurrence_count: row.is_recurring
      ? Math.max(Number(row.occurrence_count) || 0, 1)
      : row.occurrence_count,
  }
  let lines = commitmentDetailLines(proxy, asOf)
  lines = lines.map((line) => {
    if (line.label === 'Repeats' && row.is_recurring) {
      return { label: 'Repeats', value: row.frequency || 'Monthly' }
    }
    return line
  })
  const hasAmount = lines.some(
    (l) => l.label === 'Amount' || l.label === 'Installment' || l.label === 'Per period',
  )
  if (!hasAmount && ev._amount != null) {
    const dueIdx = lines.findIndex((l) => l.label === 'Due')
    lines.splice(dueIdx + 1, 0, {
      label: 'Amount',
      value: formatINR(ev._amount),
    })
  }
  if (row.is_recurring && occ && occ !== String(row.due_date || '').slice(0, 10)) {
    lines.push({ label: 'Series next', value: formatDate(row.due_date) })
  }
  return lines
}
