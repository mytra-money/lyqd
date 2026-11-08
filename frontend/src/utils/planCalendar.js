/**
 * Map LYQD plan rows → frappe-ui Calendar events (full-day by due date).
 */

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

/**
 * Flatten nested / split plan roots into calendar-ready leaf rows with due dates.
 */
export function flattenPlanForCalendar(nestedRoots) {
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

export function planRowsToCalendarEvents(nestedRoots) {
  return flattenPlanForCalendar(nestedRoots).map((row) => {
    const due = String(row.due_date).slice(0, 10)
    return {
      id: eventId(row),
      title: row.title || row.name,
      fromDate: due,
      toDate: due,
      fromTime: '00:00:00',
      toTime: '23:59:59',
      isFullDay: true,
      color: eventColor(row),
      // meta for handlers (not required by Calendar)
      _planName: row.name,
      _splitName: row.split_name || '',
      _parentPayment: row.parent_payment || '',
      _isSchedule: Boolean(row._schedule),
      _isNestChild: Boolean(row.parent_payment && !row._schedule),
      _amount: Number(row.amount) || 0,
      _cashEffect: cashEffectOf(row),
      _category: row.category || '',
      _status: row.status || 'Planned',
    }
  })
}

export function findPlanRowForEvent(nestedRoots, eventIdValue) {
  const flat = flattenPlanForCalendar(nestedRoots)
  const id = String(eventIdValue || '')
  if (id.startsWith('split:')) {
    const parts = id.split(':')
    const splitName = parts.slice(2).join(':')
    return flat.find((r) => r._schedule && r.split_name === splitName) || null
  }
  return flat.find((r) => !r._schedule && r.name === id) || null
}

export { eventId }
