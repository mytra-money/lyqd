/**
 * Home-page chart series from MIS plan rows.
 * Free-cash line = bank − policy − cumulative commitments (never includes incoming).
 * Nest math mirrors plan_card_totals: account nests collapse to signed group net.
 */

import { nestPlanRows, signedCashAmount } from '@/utils/planNest'

function ymd(d) {
  if (!d) return ''
  if (typeof d === 'string') return d.slice(0, 10)
  try {
    return new Date(d).toISOString().slice(0, 10)
  } catch {
    return ''
  }
}

function addDays(iso, n) {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

function expectedInflowAmount(row) {
  const amt = Number(row.amount || 0)
  const effect = row.cash_effect || 'Outflow'
  if (effect !== 'Inflow' && effect !== 'Setoff') return 0
  const p = row.probability != null && row.probability !== '' ? Number(row.probability) : 100
  return (amt * Math.min(Math.max(p, 0), 100)) / 100
}

function outflowAmount(row) {
  const effect = row.cash_effect || 'Outflow'
  if (effect !== 'Outflow') return 0
  return Number(row.amount || 0)
}

function signedAmount(row) {
  return signedCashAmount(row.amount, row.cash_effect)
}

function bucketDate(due, asOf, horizonEnd) {
  const day = ymd(due)
  if (!day) return null
  const bucket = day < asOf ? asOf : day
  if (bucket > horizonEnd) return null
  return bucket
}

/**
 * Dated commitment / expected-incoming grains for the horizon.
 * - GL schedule (_has_splits): each Planned installment
 * - Account nest: one grain = signed group net (children not double-counted)
 * - Recurring: each occurrence at period_amount
 * - Plain: one grain
 */
function datedPlanEvents(rows, asOf, horizonEnd) {
  const nested = nestPlanRows(rows || [])
  const events = []

  function pushEvent(due, commitments, incoming, category) {
    const date = bucketDate(due, asOf, horizonEnd)
    if (!date) return
    const c = Number(commitments) || 0
    const i = Number(incoming) || 0
    if (c < 0.005 && i < 0.005) return
    events.push({
      date,
      commitments: c,
      incoming: i,
      category: category || 'Other',
    })
  }

  for (const root of nested) {
    if ((root.status || 'Planned') !== 'Planned') continue
    const kids = (root._children || []).filter((c) => !c._recurring_occ && !c._schedule)

    // GL payment schedule — each Planned installment is its own cash event
    if (root._has_splits && kids.length) {
      for (const c of kids) {
        if ((c.status || 'Planned') !== 'Planned') continue
        pushEvent(c.due_date, outflowAmount(c), expectedInflowAmount(c), c.category || root.category)
      }
      continue
    }

    // Recurring series — expand occurrences (prefer API dates)
    if (root.is_recurring) {
      const period =
        root.period_amount != null && root.period_amount !== ''
          ? Number(root.period_amount)
          : Number(root.amount || 0)
      const dates = (root.occurrence_dates || []).map(ymd).filter(Boolean)
      const list = dates.length ? dates : root.due_date ? [ymd(root.due_date)] : []
      for (const date of list) {
        const grain = { ...root, amount: period, due_date: date }
        pushEvent(date, outflowAmount(grain), expectedInflowAmount(grain), root.category)
      }
      continue
    }

    // Account nest — collapse to signed group net once (matches plan_card_totals)
    if (kids.length) {
      const plannedKids = kids.filter((c) => (c.status || 'Planned') === 'Planned')
      const net =
        root._groupNet != null && root._groupNet !== ''
          ? Number(root._groupNet)
          : signedAmount(root) + plannedKids.reduce((s, c) => s + signedAmount(c), 0)
      const due = root.due_date || plannedKids[0]?.due_date
      if (net > 0.01) {
        pushEvent(due, net, 0, root.category)
      } else if (net < -0.01) {
        const face = Math.abs(net)
        const p =
          root.probability != null && root.probability !== '' ? Number(root.probability) : 100
        pushEvent(due, 0, (face * Math.min(Math.max(p, 0), 100)) / 100, root.category)
      }
      continue
    }

    pushEvent(root.due_date, outflowAmount(root), expectedInflowAmount(root), root.category)
  }

  return events
}

/** Cap bar count so longer horizons widen buckets instead of dropping bars. */
export const CASH_FLOW_MAX_BARS = 31

function formatDayLabel(iso) {
  const d = new Date(`${iso}T12:00:00`)
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function formatBucketLabel(startIso, endIso) {
  if (startIso === endIso) return formatDayLabel(startIso)
  return `${formatDayLabel(startIso)}–${formatDayLabel(endIso)}`
}

/**
 * Equal-width buckets over the inclusive horizon.
 * Bar count = min(days+1, MAX); never shrinks when horizon grows past the cap.
 */
function buildBuckets(start, days, maxBars = CASH_FLOW_MAX_BARS) {
  const totalDays = Math.max(1, days + 1)
  const barCount = Math.min(totalDays, Math.max(1, maxBars))
  const buckets = []
  for (let b = 0; b < barCount; b++) {
    const fromIdx = Math.floor((b * totalDays) / barCount)
    const toIdx = Math.floor(((b + 1) * totalDays) / barCount) - 1
    const from = addDays(start, fromIdx)
    const to = addDays(start, toIdx)
    buckets.push({
      index: b,
      fromIdx,
      toIdx,
      from,
      to,
      label: formatBucketLabel(from, to),
    })
  }
  return buckets
}

function bucketIndexForDay(dayIndex, totalDays, barCount) {
  if (barCount <= 1) return 0
  return Math.min(barCount - 1, Math.floor((dayIndex * barCount) / totalDays))
}

/**
 * Horizon cash-flow series for the home BarChart
 * (stacked bars + free-cash + expected-cash lines).
 *
 * free_cash = bank − policy − cumulative commitments (never includes incoming)
 * expected_cash = free_cash + cumulative expected incoming
 *
 * @returns {{ date: string, label: string, commitments: number, incoming: number, free_cash: number, expected_cash: number }[]}
 */
export function buildHorizonCashFlowSeries({
  rows,
  asOf,
  horizonDays,
  bankCash,
  policyReserves,
}) {
  const start = ymd(asOf) || new Date().toISOString().slice(0, 10)
  const days = Math.max(0, Number(horizonDays) || 0)
  const end = addDays(start, days)
  const totalDays = days + 1
  const buckets = buildBuckets(start, days)
  const barCount = buckets.length
  const events = datedPlanEvents(rows, start, end)

  const daily = new Map()
  for (let i = 0; i <= days; i++) {
    const date = addDays(start, i)
    daily.set(date, { date, commitments: 0, incoming: 0 })
  }
  for (const ev of events) {
    const row = daily.get(ev.date)
    if (!row) continue
    row.commitments += ev.commitments
    row.incoming += ev.incoming
  }

  const series = buckets.map((b) => ({
    date: b.from,
    label: b.label,
    commitments: 0,
    incoming: 0,
    free_cash: 0,
    expected_cash: 0,
  }))

  let freeRunning = Number(bankCash || 0) - Number(policyReserves || 0)
  let incomingCum = 0

  for (let i = 0; i <= days; i++) {
    const date = addDays(start, i)
    const day = daily.get(date)
    freeRunning -= day.commitments
    incomingCum += day.incoming
    const bi = bucketIndexForDay(i, totalDays, barCount)
    const row = series[bi]
    row.commitments += day.commitments
    row.incoming += day.incoming
    // End-of-bucket positions (last day in the bucket wins)
    row.free_cash = freeRunning
    row.expected_cash = freeRunning + incomingCum
  }

  return series.map((row) => ({
    ...row,
    commitments: Math.round(row.commitments * 100) / 100,
    incoming: Math.round(row.incoming * 100) / 100,
    free_cash: Math.round(row.free_cash * 100) / 100,
    expected_cash: Math.round(row.expected_cash * 100) / 100,
  }))
}

function categoryMixFromEvents(events, field) {
  const byCat = new Map()
  for (const ev of events) {
    const amt = Number(ev[field]) || 0
    if (!(amt > 0.01)) continue
    const key = ev.category || 'Other'
    byCat.set(key, (byCat.get(key) || 0) + amt)
  }
  return [...byCat.entries()]
    .map(([category, amount]) => ({
      category,
      amount: Math.round(amount * 100) / 100,
    }))
    .sort((a, b) => b.amount - a.amount)
}

/**
 * Commitments by category for the horizon (Planned outflows / nest nets).
 */
export function buildCommitmentCategoryMix({ rows, asOf, horizonDays }) {
  const start = ymd(asOf) || new Date().toISOString().slice(0, 10)
  const end = addDays(start, Math.max(0, Number(horizonDays) || 0))
  return categoryMixFromEvents(datedPlanEvents(rows, start, end), 'commitments')
}

/**
 * Expected incoming by category for the horizon (probability-weighted).
 */
export function buildIncomingCategoryMix({ rows, asOf, horizonDays }) {
  const start = ymd(asOf) || new Date().toISOString().slice(0, 10)
  const end = addDays(start, Math.max(0, Number(horizonDays) || 0))
  return categoryMixFromEvents(datedPlanEvents(rows, start, end), 'incoming')
}

export function formatChartINR(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(n)
  } catch {
    return `₹${Math.round(n).toLocaleString('en-IN')}`
  }
}
