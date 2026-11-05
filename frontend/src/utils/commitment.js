import { formatDate, formatINR } from '@/utils/format'

export function daysUntil(due, asOf) {
  if (!due) return null
  const a = new Date(asOf || new Date().toISOString().slice(0, 10))
  const b = new Date(due)
  return Math.round((b - a) / 86400000)
}

export function isOverdue(due, asOf) {
  const d = daysUntil(due, asOf)
  return d !== null && d < 0
}

export function dueLabel(due, asOf) {
  if (!due) return 'No due date'
  const d = daysUntil(due, asOf)
  if (d === null) return formatDate(due)
  if (d < 0) return `Overdue · ${formatDate(due)}`
  if (d === 0) return 'Due today'
  if (d === 1) return 'Due tomorrow'
  if (d <= 7) return `Due in ${d}d · ${formatDate(due)}`
  return `Due ${formatDate(due)}`
}

export function frequencyUnit(frequency) {
  const f = (frequency || 'Monthly').toLowerCase()
  if (f === 'weekly') return 'week'
  if (f === 'quarterly') return 'quarter'
  return 'month'
}

export function shortAccount(account) {
  if (!account) return ''
  const parts = String(account).split(' - ')
  if (parts.length < 2) return String(account)
  return parts.slice(0, -1).join(' - ')
}

/** Recurring outside the forecast horizon expands to ₹0 reserved — still show per period. */
export function displayPlanAmount(row) {
  if (row?.is_recurring && !(row.occurrence_count > 0) && row.period_amount != null) {
    return row.period_amount
  }
  return row?.amount
}

export function isInflowEffect(effect) {
  return effect === 'Inflow' || effect === 'Setoff'
}

export function commitmentDetailLines(row, asOf) {
  const lines = []
  if (row.due_date) lines.push({ label: 'Due', value: dueLabel(row.due_date, asOf) })
  if (row.category) lines.push({ label: 'Category', value: row.category })
  if (row.status) lines.push({ label: 'Status', value: row.status })
  if (row.cash_effect) lines.push({ label: 'Effect', value: row.cash_effect })
  if (row.is_recurring) {
    lines.push({
      label: 'Repeats',
      value:
        row.occurrence_count > 0
          ? `${row.frequency || 'Monthly'} · ${row.occurrence_count} in horizon`
          : `${row.frequency || 'Monthly'} · outside horizon`,
    })
    if (row.occurrence_count > 1) {
      const per =
        row.period_amount != null
          ? row.period_amount
          : row.amount / row.occurrence_count
      lines.push({ label: 'Per period', value: formatINR(per) })
    }
  }
  if (row._childCount) {
    lines.push({
      label: 'GL total',
      value:
        (isInflowEffect(row.cash_effect) ? '−' : '') + formatINR(row.amount),
    })
  }
  if (row.balance_as_of) {
    lines.push({ label: 'Frozen as of', value: formatDate(row.balance_as_of) })
  }
  if (row.source_doctype) {
    lines.push({
      label: 'Books ref',
      value: `${row.source_doctype} ${row.source_name || ''}`.trim(),
    })
  }
  if (row.source_account) {
    lines.push({ label: 'Account', value: shortAccount(row.source_account) })
  }
  if (row.notes) lines.push({ label: 'Notes', value: row.notes })
  return lines
}
