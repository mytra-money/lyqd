import { watch } from 'vue'
import { useStorage } from '@vueuse/core'
import { useCompanyStore } from '@/stores/company'

/**
 * Shared forecast horizon (days). Free-form 1–365; UI suggests 7/14/30/60.
 * Persists in the browser so Cash position / Free cash / Invest stay aligned.
 */
export function useHorizon() {
  const company = useCompanyStore()
  const horizon = useStorage('lyqd_horizon_days', 7)

  watch(
    () => company.settings?.default_forecast_horizon_days,
    (days) => {
      // Only seed once when the user has never set a preference
      if (!days) return
      try {
        if (localStorage.getItem('lyqd_horizon_days') == null) {
          horizon.value = Math.min(365, Math.max(1, Number(days) || 7))
        }
      } catch {
        /* ignore */
      }
    },
    { immediate: true },
  )

  return { horizon }
}
