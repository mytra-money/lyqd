import { call } from 'frappe-ui'

/**
 * Load company payment categories for the plan form.
 * @param {string} company
 * @param {string} [cashEffect] Outflow | Inflow | Setoff
 * @returns {Promise<{ label: string, value: string }[]>}
 */
export async function fetchPaymentCategoryOptions(company, cashEffect) {
  if (!company) return []
  const rows = await call('lyqd.api.spa.list_payment_categories', {
    company,
    cash_effect: cashEffect || undefined,
  })
  return (rows || []).map((r) => ({
    label: r.category_name,
    value: r.category_name,
  }))
}

/** Fallback labels matching seeded defaults (offline / empty company). */
export const DEFAULT_CATEGORY_LABELS = [
  'Salary',
  'Import-LC',
  'Vendor',
  'Customer',
  'Tax',
  'Loan',
  'FD Maturity',
  'Loan Proceeds',
  'Other',
]
