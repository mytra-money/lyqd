/**
 * Signed reserved cash from an explanation upcoming line.
 * Outflow (−) reserves; Setoff (+) reduces reserve.
 */
function signedReserved(line) {
  const amt = Number(line.amount || 0)
  return line.sign === '+' ? -amt : amt
}

/**
 * Prefer already-nested surplus explanation; otherwise rebuild groups from
 * upcoming_payments.parent_payment (covers older frozen runs).
 */
function nestExplanationLines(lines, upcomingPayments = []) {
  const list = lines || []
  if (!list.length) return []
  if (list.some((l) => l.child_count || (l.children && l.children.length))) {
    return list
  }

  const payments = upcomingPayments || []
  const byName = new Map(payments.map((p) => [p.name, p]))
  const childrenOf = new Map()
  for (const p of payments) {
    const parent = p.parent_payment
    if (parent && byName.has(parent) && parent !== p.name) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, [])
      childrenOf.get(parent).push(p.name)
    }
  }
  if (!childrenOf.size) return list

  const childNames = new Set([...childrenOf.values()].flat())
  const lineByRef = new Map(
    list.filter((l) => l.kind === 'upcoming' && l.ref_name).map((l) => [l.ref_name, l]),
  )

  const out = []
  for (const line of list) {
    if (line.kind !== 'upcoming') {
      out.push(line)
      continue
    }
    if (childNames.has(line.ref_name)) continue

    const kidNames = childrenOf.get(line.ref_name) || []
    if (!kidNames.length) {
      out.push(line)
      continue
    }

    const kids = kidNames.map((n) => lineByRef.get(n)).filter(Boolean)
    const net = signedReserved(line) + kids.reduce((s, c) => s + signedReserved(c), 0)
    out.push({
      ...line,
      gl_amount: Number(line.amount || 0),
      gl_sign: line.sign,
      amount: Math.abs(net),
      sign: net >= 0 ? '-' : '+',
      child_count: kids.length,
      children: kids,
    })
  }
  return out
}

/**
 * Build payment stubs for nesting. Uses frozen upcoming_payments when they
 * already carry parent_payment; otherwise overlays live parentByName (name → parent).
 */
function paymentsForNest(explanation, upcomingPayments, parentByName = {}) {
  const frozen = upcomingPayments || []
  const hasFrozenParents = frozen.some((p) => p.parent_payment)
  if (hasFrozenParents) return frozen

  const names = new Set()
  for (const p of frozen) {
    if (p.name) names.add(p.name)
  }
  for (const line of explanation || []) {
    if (line.kind === 'upcoming' && line.ref_name) names.add(line.ref_name)
  }
  return [...names].map((name) => ({
    name,
    parent_payment: parentByName[name] || null,
  }))
}

/**
 * Load display lines from a Surplus Run doc (explanation_json preferred).
 * parentByName: live Upcoming Payment name → parent_payment for older frozen runs.
 */
export function surplusRunExplanationLines(doc, parentByName = {}) {
  if (!doc) return []
  try {
    const raw = doc.explanation_json
    if (raw) {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      const explanation = parsed.explanation || []
      if (explanation.length) {
        return nestExplanationLines(
          explanation,
          paymentsForNest(explanation, parsed.upcoming_payments || [], parentByName),
        )
      }
    }
  } catch {
    /* fall through */
  }
  if (Array.isArray(doc.lines) && doc.lines.length) {
    const mapped = doc.lines.map((l) => ({
      kind: l.kind,
      label: l.label,
      amount: l.amount,
      sign: l.sign,
      category: l.category,
      due_date: l.due_date,
      ref_name: l.ref_name,
      gl_amount: l.gl_amount,
      gl_sign: l.gl_sign,
      child_count: l.child_count || 0,
      children: l.children || [],
    }))
    return nestExplanationLines(
      mapped,
      paymentsForNest(mapped, [], parentByName),
    )
  }
  return []
}
