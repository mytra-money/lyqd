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
    const parent = row.parent_payment
    if (parent && byName.has(parent) && parent !== row.name) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, [])
      childrenOf.get(parent).push(row)
    } else {
      roots.push(row)
    }
  }

  return roots.map((root) => {
    const kids = (childrenOf.get(root.name) || []).filter(isVisibleNestedChild)
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

/**
 * Parent + nested children for cascade actions (mark paid / refresh).
 */
export function groupMembers(row) {
  if (!row) return []
  const kids = row._children || []
  return [row, ...kids]
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
