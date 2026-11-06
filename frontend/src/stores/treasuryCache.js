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

  function _bucketMap(bucket) {
    return bucket === 'mis'
      ? mis
      : bucket === 'cash'
        ? cash
        : bucket === 'surplus'
          ? surplus
          : bucket === 'plan'
            ? plan
            : recommendations
  }

  async function _fetch(bucket, key, loader, loadingRef, { silent = false } = {}) {
    if (inflight[bucket].has(key)) {
      return inflight[bucket].get(key)
    }
    if (!silent) loadingRef.value = true
    const promise = (async () => {
      const target = _bucketMap(bucket)
      try {
        const data = await loader()
        target[key] = { data, fetchedAt: Date.now(), error: null }
        return data
      } catch (e) {
        // Keep a stub so the UI can leave "Loading…" and show the error
        const msg =
          e?.messages?.[0] || e?.message || e?.exc_type || 'Could not load from books'
        const prev = target[key]?.data
        target[key] = {
          data:
            prev ||
            (bucket === 'recs'
              ? { enabled: true, items: [], message: String(msg).slice(0, 400) }
              : null),
          fetchedAt: Date.now(),
          error: String(msg).slice(0, 400),
        }
        throw e
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

  function getRecommendationsError(company) {
    return recommendations[cacheKey([company])]?.error || null
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
        const rows = await call('lyqd.api.spa.list_upcoming_payments', { company })
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

  async function ensureRecommendations({ company, force = false, silent = null } = {}) {
    if (!company) return null
    const key = cacheKey([company])
    const entry = recommendations[key]
    if (!force && isFresh(entry)) return entry.data
    // Keep existing list on screen when refreshing after accept/ignore (no flash).
    const useSilent =
      silent != null ? !!silent && !!entry?.data : !!(entry?.data && !force)
    const promise = _fetch(
      'recs',
      key,
      () => call('lyqd.api.spa.get_upcoming_recommendations', { company }),
      recsLoading,
      { silent: useSilent },
    )
    if (useSilent) {
      promise.catch(() => {})
      return entry.data
    }
    return promise
  }

  /**
   * Drop a books source from the cached From-books list (accept / ignore)
   * without clearing the whole payload — avoids a Loading suggestions flash.
   */
  function removeRecommendationSource(company, sourceDoctype, sourceName) {
    if (!company || !sourceDoctype || !sourceName) return
    const key = cacheKey([company])
    const entry = recommendations[key]
    if (!entry?.data?.items) return
    const dt = String(sourceDoctype)
    const nm = String(sourceName)
    const items = entry.data.items.filter(
      (i) => !(String(i.source_doctype) === dt && String(i.source_name) === nm),
    )
    if (items.length === entry.data.items.length) return
    recommendations[key] = {
      ...entry,
      data: { ...entry.data, items },
      error: null,
    }
  }

  function _clearCompanyBucket(bucket, company = null) {
    for (const k of Object.keys(bucket)) {
      if (!company || k === company || k.startsWith(`${company}::`)) {
        delete bucket[k]
      }
    }
  }

  /** After mutations that change cash / free cash only. */
  function invalidateCashRelated(company = null) {
    _clearCompanyBucket(mis, company)
    _clearCompanyBucket(cash, company)
    _clearCompanyBucket(surplus, company)
  }

  /**
   * After plan edits that do not change which books sources are accepted
   * (amount / due / probability / mark paid / freeze / split). Keeps From-books
   * suggestions cached so Commitments does not flash-reload them.
   */
  function invalidatePlanOnly(company = null) {
    invalidateCashRelated(company)
    _clearCompanyBucket(plan, company)
  }

  /**
   * After mutations that can change the accepted set (accept / cancel / books
   * sync that cancels rows). Clears plan + From-books recommendations.
   */
  function invalidatePlanRelated(company = null) {
    invalidatePlanOnly(company)
    _clearCompanyBucket(recommendations, company)
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
    getRecommendationsError,
    ensureMis,
    ensureCash,
    ensureSurplus,
    ensurePlan,
    ensureRecommendations,
    removeRecommendationSource,
    invalidateCashRelated,
    invalidatePlanOnly,
    invalidatePlanRelated,
    invalidateAll,
  }
})
