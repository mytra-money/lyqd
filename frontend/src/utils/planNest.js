/**
 * Signed cash amount for free-cash math (Setoff reduces).
 */
function signedAmount(row) {
  const amt = Number(row.amount || 0)
  return (row.cash_effect || 'Outflow') === 'Setoff' ? -amt : amt
}

/**
 * Nest plan rows under parents. Roots get `_childCount`, `_groupNet`, `_children`.
 * Children stay on the parent (not flattened) so the UI can collapse them.
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
    const kids = childrenOf.get(root.name) || []
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
