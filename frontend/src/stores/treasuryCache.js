import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { call } from 'frappe-ui'

/** Soft TTL — show cached data immediately, refresh in background when stale. */
const TTL_MS = 45_000

function cacheKey(parts) {
  return parts.map((p) => String(p ?? '')).join('::')
}

function isFresh(entry) {
  return !!entry && Date.now() - entry.fetchedAt < TTL_MS
}

/**
 * Session cache for Cash position / Commitments / Free cash / Bank cash.
 * Pages KeepAlive + this store avoid re-hitting slow APIs on every navigation.
 */
export const useTreasuryCacheStore = defineStore('treasuryCache', () => {
  const mis = reactive({})
  const cash = reactive({})
  const surplus = reactive({})
  const plan = reactive({})
  const recommendations = reactive({})

  const misLoading = ref(false)
  const cashLoading = ref(false)
  const surplusLoading = ref(false)
  const planLoading = ref(false)
  const recsLoading = ref(false)

  const inflight = {
    mis: new Map(),
    cash: new Map(),
    surplus: new Map(),
    plan: new Map(),
    recs: new Map(),
  }

  async function _fetch(bucket, key, loader, loadingRef, { silent = false } = {}) {
    if (inflight[bucket].has(key)) {
      return inflight[bucket].get(key)
    }
    if (!silent) loadingRef.value = true
    const promise = (async () => {
      try {
        const data = await loader()
        const target =
          bucket === 'mis'
            ? mis
            : bucket === 'cash'
              ? cash
              : bucket === 'surplus'
                ? surplus
                : bucket === 'plan'
                  ? plan
                  : recommendations
        target[key] = { data, fetchedAt: Date.now() }
        return data
      } finally {
        inflight[bucket].delete(key)
        if (!silent) {
          loadingRef.value = inflight[bucket].size > 0
        }
      }
    })()
    inflight[bucket].set(key, promise)
    return promise
  }

  function getMis(company, horizonDays) {
    return mis[cacheKey([company, horizonDays])]?.data || null
  }

  function getCash(company) {
    return cash[cacheKey([company])]?.data || null
  }

  function getSurplus(company, horizonDays) {
    return surplus[cacheKey([company, horizonDays])]?.data || null
  }

  function getPlan(company) {
    return plan[cacheKey([company])]?.data || null
  }

  function getRecommendations(company) {
    return recommendations[cacheKey([company])]?.data || null
  }

  /**
   * @param {{ company: string, horizonDays?: number|string, force?: boolean }} opts
   */
  async function ensureMis({ company, horizonDays = 7, force = false } = {}) {
    if (!company) return null
    const key = cacheKey([company, horizonDays])
    const entry = mis[key]
    if (!force && isFresh(entry)) return entry.data
    const silent = !!(entry?.data && !force)
    const promise = _fetch(
      'mis',
      key,
      () =>
        call('lyqd.api.spa.get_morning_mis', {
          company,
          horizon_days: horizonDays,
        }),
      misLoading,
      { silent },
    )
    if (silent) {
      promise.catch(() => {})
      return entry.data
    }
    return promise
  }

  async function ensureCash({ company, force = false } = {}) {
    if (!company) return null
    const key = cacheKey([company])
    const entry = cash[key]
    if (!force && isFresh(entry)) return entry.data
    const silent = !!(entry?.data && !force)
    const promise = _fetch(
      'cash',
      key,
      () => call('lyqd.api.spa.get_cash_detail', { company }),
      cashLoading,
      { silent },
    )
    if (silent) {
      promise.catch(() => {})
      return entry.data
    }
    return promise
  }

  async function ensureSurplus({ company, horizonDays = 7, force = false } = {}) {
    if (!company) return null
    const key = cacheKey([company, horizonDays])
    const entry = surplus[key]
    if (!force && isFresh(entry)) return entry.data
    const silent = !!(entry?.data && !force)
    const promise = _fetch(
      'surplus',
      key,
      () =>
        call('lyqd.api.dashboard.get_surplus_explanation', {
          company,
          horizon_days: horizonDays,
        }),
      surplusLoading,
      { silent },
    )
    if (silent) {
      promise.catch(() => {})
      return entry.data
    }
    return promise
  }

  async function ensurePlan({ company, force = false } = {}) {
    if (!company) return null
    const key = cacheKey([company])
    const entry = plan[key]
    if (!force && isFresh(entry)) return entry.data
    const silent = !!(entry?.data && !force)
    const promise = _fetch(
      'plan',
      key,
      async () => {
        const rows = await call('frappe.client.get_list', {
          doctype: 'LYQD Upcoming Payment',
          fields: [
            'name',
            'title',
            'category',
            'due_date',
            'amount',
            'cash_effect',
            'status',
            'notes',
            'company',
            'source_doctype',
            'source_name',
            'source_account',
            'last_synced_on',
          ],
          filters: { company },
          order_by: 'due_date asc',
          limit_page_length: 500,
        })
        return rows || []
      },
      planLoading,
      { silent },
    )
    if (silent) {
      promise.catch(() => {})
      return entry.data
    }
    return promise
  }

  async function ensureRecommendations({ company, force = false } = {}) {
    if (!company) return null
    const key = cacheKey([company])
    const entry = recommendations[key]
    if (!force && isFresh(entry)) return entry.data
    const silent = !!(entry?.data && !force)
    const promise = _fetch(
      'recs',
      key,
      () => call('lyqd.api.spa.get_upcoming_recommendations', { company }),
      recsLoading,
      { silent },
    )
    if (silent) {
      promise.catch(() => {})
      return entry.data
    }
    return promise
  }

  /** After mutations that change cash / plan / free cash. */
  function invalidateCashRelated(company = null) {
    const clearMatching = (bucket) => {
      for (const k of Object.keys(bucket)) {
        if (!company || k === company || k.startsWith(`${company}::`)) {
          delete bucket[k]
        }
      }
    }
    clearMatching(mis)
    clearMatching(cash)
    clearMatching(surplus)
  }

  function invalidatePlanRelated(company = null) {
    invalidateCashRelated(company)
    for (const k of Object.keys(plan)) {
      if (!company || k === company || k.startsWith(`${company}::`)) delete plan[k]
    }
    for (const k of Object.keys(recommendations)) {
      if (!company || k === company || k.startsWith(`${company}::`)) delete recommendations[k]
    }
  }

  function invalidateAll() {
    for (const bucket of [mis, cash, surplus, plan, recommendations]) {
      for (const k of Object.keys(bucket)) delete bucket[k]
    }
  }

  return {
    TTL_MS,
    misLoading,
    cashLoading,
    surplusLoading,
    planLoading,
    recsLoading,
    getMis,
    getCash,
    getSurplus,
    getPlan,
    getRecommendations,
    ensureMis,
    ensureCash,
    ensureSurplus,
    ensurePlan,
    ensureRecommendations,
    invalidateCashRelated,
    invalidatePlanRelated,
    invalidateAll,
  }
})
