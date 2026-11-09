import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/** Paths that host the plan calendar dialog in-place. */
export function isPlanCalendarHostPath(path) {
  return path === '/' || path === '' || path === '/upcoming'
}

/** Prefer staying on Commitments when already there; otherwise home. */
export function planCalendarPathFor(path) {
  return path === '/upcoming' ? '/upcoming' : '/'
}

function pathMatchesHost(path, hostPath) {
  if (hostPath === '/' || hostPath === '') {
    return path === '/' || path === ''
  }
  return path === hostPath
}

/**
 * Open/close plan calendar via ``?view=calendar`` on this page.
 * Pass ``hostPath`` ('/' or '/upcoming') so keep-alive siblings don't both open.
 */
export function usePlanCalendar(hostPath = '/') {
  const route = useRoute()
  const router = useRouter()
  const showPlanCalendar = ref(false)

  function syncCalendarQuery(open) {
    const q = { ...route.query }
    if (open) q.view = 'calendar'
    else delete q.view
    const path = pathMatchesHost(route.path, hostPath)
      ? route.path || hostPath
      : hostPath
    router.replace({ path: path === '' ? '/' : path, query: q })
  }

  function onPlanCalendarOpenChange(open) {
    showPlanCalendar.value = !!open
    syncCalendarQuery(showPlanCalendar.value)
  }

  function syncCalendarFromRoute() {
    showPlanCalendar.value =
      pathMatchesHost(route.path, hostPath) && route.query.view === 'calendar'
  }

  function openPlanCalendarHere() {
    showPlanCalendar.value = true
    syncCalendarQuery(true)
  }

  watch(
    () => [route.path, route.query.view],
    () => syncCalendarFromRoute(),
    { immediate: true },
  )

  return {
    showPlanCalendar,
    onPlanCalendarOpenChange,
    syncCalendarFromRoute,
    syncCalendarQuery,
    openPlanCalendarHere,
  }
}
