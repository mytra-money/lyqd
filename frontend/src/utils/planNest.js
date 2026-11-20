/**
 * Signed cash amount for free-cash math (Setoff / Inflow reduce reserve).
 */
export function signedCashAmount(amount, cashEffect) {
  const amt = Number(amount || 0)
  return (cashEffect || 'Outflow') === 'Outflow' ? amt : -amt
}

function signedAmount(row) {
  return signedCashAmount(row.amount, row.cash_effect)
}

/** Near-zero Account (GL) balances are omitted — same as non-nested books suggestions. */
function isVisibleNestedChild(row) {
  if ((row?.source_doctype || '') === 'Account' && Math.abs(Number(row.amount || 0)) <= 0.01) {
    return false
  }
  return true
}

/**
 * Nest plan rows under parents. Roots get `_childCount`, `_groupNet`, `_children`.
 * Children stay on the parent (not flattened) so the UI can collapse them.
 * Zero-balance child GLs are hidden (kept off the nested list).
 */
export function nestPlanRows(rows) {
  const list = rows || []
  const byName = new Map(list.map((r) => [r.name, r]))
  const childrenOf = new Map()
  const roots = []

  for (const row of list) {
    // GL schedule children are already attached on the parent from the API
    if (row._has_splits && Array.isArray(row._children)) {
      roots.push(row)
      continue
    }
    const parent = row.parent_payment
    if (parent && byName.has(parent) && parent !== row.name) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, [])
      childrenOf.get(parent).push(row)
    } else {
      roots.push(row)
    }
  }

  function byDue(a, b) {
    const da = String(a?.due_date || '9999-99-99')
    const db = String(b?.due_date || '9999-99-99')
    if (da !== db) return da < db ? -1 : 1
    return Number(b?.amount || 0) - Number(a?.amount || 0)
  }

  const nested = roots.map((root) => {
    if (root._has_splits && Array.isArray(root._children)) {
      const kids = (root._children || []).filter(isVisibleNestedChild).slice().sort(byDue)
      const groupNet =
        root._groupNet != null
          ? root._groupNet
          : kids
              .filter((c) => (c.status || 'Planned') === 'Planned')
              .reduce((s, c) => s + signedAmount(c), 0)
      return {
        ...root,
        _child: false,
        _childCount: kids.length,
        _groupNet: groupNet,
        _children: kids.map((child) => ({
          ...child,
          _child: true,
          _childCount: 0,
          _groupNet: null,
          _children: [],
        })),
      }
    }
    const kids = (childrenOf.get(root.name) || []).filter(isVisibleNestedChild).slice().sort(byDue)
    // Prefer stored parent.group_net on nest roots (0 means non-nest / cleared).
    const storedNet =
      root.group_net != null && root.group_net !== '' ? Number(root.group_net) : null
    const groupNet =
      kids.length > 0
        ? Number.isFinite(storedNet)
          ? storedNet
          : signedAmount(root) + kids.reduce((s, c) => s + signedAmount(c), 0)
        : null
    return {
      ...root,
      _child: false,
      _childCount: kids.length,
      _groupNet: groupNet,
      _children: kids.map((child) => ({
        ...child,
        _child: true,
        _childCount: 0,
        _groupNet: null,
        _children: [],
      })),
    }
  })

  return nested.slice().sort(byDue)
}

/**
 * Attach expandable occurrence children for recurring series (home Plan / Commitments).
 *
 * Collapsed row keeps the horizon total; expand shows each due + period amount
 * (calendar-style), without creating extra docs. Skips rows that are already
 * groups / GL splits.
 */
export function enrichRecurringOccurrences(nestedRoots) {
  return (nestedRoots || []).map((root) => {
    if (!root || root._childCount > 0) return root
    if (!root.is_recurring) return root
    const dates = (root.occurrence_dates || [])
      .map((d) => String(d || '').slice(0, 10))
      .filter(Boolean)
    if (dates.length <= 1) return root

    const period =
      root.period_amount != null && root.period_amount !== ''
        ? Number(root.period_amount)
        : (Number(root.amount) || 0) / dates.length

    const kids = dates.map((date) => ({
      name: `${root.name}::occ::${date}`,
      title: root.title,
      due_date: date,
      amount: period,
      period_amount: period,
      cash_effect: root.cash_effect || 'Outflow',
      status: 'Planned',
      probability: root.probability,
      category: root.category,
      is_recurring: 0,
      _recurring_occ: true,
      _child: true,
      _childCount: 0,
      _groupNet: null,
      _children: [],
    }))

    return {
      ...root,
      _recurring: true,
      _childCount: kids.length,
      _children: kids,
      // Never treat occurrence expand as an Account nest — direction uses cash_effect × amount.
      _groupNet: null,
    }
  })
}

/**
 * Parent + nested children for cascade actions (mark paid / refresh).
 * Synthetic recurring occurrence rows are display-only and excluded.
 */
export function groupMembers(row) {
  if (!row) return []
  const kids = (row._children || []).filter((c) => !c._recurring_occ)
  return [row, ...kids]
}

function isRealChild(row) {
  return !!row && !row._recurring_occ
}

function memberStatus(row) {
  return row?.status || 'Planned'
}

function recomputeVisibleGroupNet(root, kids) {
  if (root?._has_splits) {
    return kids
      .filter((c) => memberStatus(c) === 'Planned')
      .reduce((s, c) => s + signedAmount(c), 0)
  }
  if (!(kids || []).length) return null
  return signedAmount(root) + kids.reduce((s, c) => s + signedAmount(c), 0)
}

/**
 * Nest first, then filter groups by view — keeps nest roots intact when only some
 * members are Paid (avoids orphan children on the Paid tab).
 *
 * @param {Array} allRows full plan list (all statuses)
 * @param {'active'|'overdue'|'paid'|'ignored'} view
 * @param {(due: string) => boolean} [isOverdueFn]
 */
export function filterPlanGroupsByView(allRows, view, isOverdueFn) {
  const nested = nestPlanRows(allRows || [])
  const out = []

  for (const root of nested) {
    const allKids = (root._children || []).filter(isRealChild)
    const schedule = !!root._has_splits

    if (view === 'paid') {
      const paidKids = allKids.filter((c) => memberStatus(c) === 'Paid')
      const rootPaid = memberStatus(root) === 'Paid'
      if (!rootPaid && !paidKids.length) continue
      const kids = paidKids
      let paidNet = kids.reduce((s, c) => s + signedAmount(c), 0)
      if (rootPaid) paidNet += signedAmount(root)
      out.push({
        ...root,
        _childCount: kids.length,
        _groupNet: schedule || kids.length || rootPaid ? paidNet : null,
        _children: kids.map((child) => ({
          ...child,
          _child: true,
          _childCount: 0,
          _groupNet: null,
          _children: [],
        })),
      })
      continue
    }

    if (view === 'ignored') {
      const ignoredKids = allKids.filter((c) => memberStatus(c) === 'Ignored')
      const rootIgnored = memberStatus(root) === 'Ignored'
      if (!rootIgnored && !ignoredKids.length) continue
      const kids = ignoredKids
      out.push({
        ...root,
        _childCount: kids.length,
        _groupNet: recomputeVisibleGroupNet(root, kids),
        _children: kids.map((child) => ({
          ...child,
          _child: true,
          _childCount: 0,
          _groupNet: null,
          _children: [],
        })),
      })
      continue
    }

    // active / overdue — Planned members only
    const plannedKids = allKids.filter((c) => memberStatus(c) === 'Planned')
    const rootPlanned = memberStatus(root) === 'Planned'
    if (!rootPlanned && !plannedKids.length) continue

    let kids = plannedKids
    if (view === 'overdue') {
      const overdueFn = typeof isOverdueFn === 'function' ? isOverdueFn : () => false
      const rootOverdue = rootPlanned && overdueFn(root.due_date)
      kids = plannedKids.filter((c) => overdueFn(c.due_date))
      if (!rootOverdue && !kids.length) continue
    }

    out.push({
      ...root,
      status: rootPlanned ? root.status : kids[0]?.status || root.status,
      _childCount: kids.length,
      _groupNet: recomputeVisibleGroupNet(
        root,
        // Active display net from Planned kids (+ root grain when Planned)
        rootPlanned ? kids : kids,
      ),
      _children: kids.map((child) => ({
        ...child,
        _child: true,
        _childCount: 0,
        _groupNet: null,
        _children: [],
      })),
    })
  }

  return out
}

/**
 * Signed reserve for filters: nest/split ``_groupNet`` when present, else row amount.
 * Outflow net &gt; 0; Inflow/Setoff net &lt; 0.
 *
 * Recurring series (incl. expanded occurrence children) always use
 * ``cash_effect`` × horizon amount — or per-period amount when outside the
 * forecast horizon (amount is ₹0). Never classify repeats via nest ``_groupNet``.
 */
export function planSignedNet(row) {
  if (!row) return 0
  if (row.is_recurring || row._recurring) {
    const horizonAmt = Number(row.amount)
    const period =
      row.period_amount != null && row.period_amount !== ''
        ? Number(row.period_amount)
        : null
    const amt =
      Number.isFinite(horizonAmt) && Math.abs(horizonAmt) > 0.01
        ? horizonAmt
        : Number.isFinite(period)
          ? period
          : horizonAmt || 0
    return signedCashAmount(amt, row.cash_effect)
  }
  if (
    row._childCount &&
    row._groupNet != null &&
    row._groupNet !== '' &&
    Number.isFinite(Number(row._groupNet))
  ) {
    return Number(row._groupNet)
  }
  return signedCashAmount(row.amount, row.cash_effect)
}

/**
 * Nest "From books" suggestion rows using Settings ``parent_account``
 * (Account-grain only). Voucher rows stay roots.
 */
export function nestRecommendationRows(rows) {
  const list = rows || []
  const byAccount = new Map()
  for (const row of list) {
    if (row.source_doctype === 'Account' && row.source_name) {
      byAccount.set(row.source_name, row)
    }
  }

  const childrenOf = new Map()
  const roots = []

  for (const row of list) {
    const parentAcc = row.parent_account
    if (
      row.source_doctype === 'Account' &&
      parentAcc &&
      byAccount.has(parentAcc) &&
      parentAcc !== row.source_name
    ) {
      if (!childrenOf.has(parentAcc)) childrenOf.set(parentAcc, [])
      childrenOf.get(parentAcc).push(row)
    } else {
      roots.push(row)
    }
  }

  return roots.map((root) => {
    const kids =
      root.source_doctype === 'Account' ? childrenOf.get(root.source_name) || [] : []
    const groupNet =
      kids.length > 0
        ? signedAmount(root) + kids.reduce((s, c) => s + signedAmount(c), 0)
        : null
    return {
      ...root,
      _child: false,
      _childCount: kids.length,
      _groupNet: groupNet,
      _children: kids.map((child) => ({
        ...child,
        _child: true,
        _childCount: 0,
        _groupNet: null,
        _children: [],
      })),
    }
  })
}

/** Stable list key for a recommendation / nested child. */
export function recommendationKey(item) {
  if (!item) return ''
  return `${item.source_doctype || ''}:${item.source_name || ''}:${item.source_row || ''}:${item.account || ''}`
}
