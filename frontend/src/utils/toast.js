/**
 * frappe-ui toast + reka-ui ToastRoot can stay open when the viewport
 * pause/resume cycle sticks. Schedule an explicit remove so toasts dismiss.
 *
 * Always import `{ toast }` from `@/utils/toast` (not `frappe-ui`) so create
 * and `<Toasts />` share one toastsState instance.
 */
import { toast as baseToast, Toasts } from '@/utils/frappeToastHost'

export { Toasts }

const DEFAULT_SECONDS = 5

/** Original create before any LYQD patching (avoids recursive install). */
const originalCreate = baseToast.create.bind(baseToast)

function dismissAfter(id, seconds) {
  if (!id || !(seconds > 0)) return
  window.setTimeout(() => {
    try {
      baseToast.remove(id)
    } catch (_) {
      /* toast already gone */
    }
  }, seconds * 1000)
}

function durationSeconds(options = {}) {
  if (options.duration != null && options.duration !== '') {
    const n = Number(options.duration)
    return Number.isFinite(n) ? n : DEFAULT_SECONDS
  }
  return DEFAULT_SECONDS
}

function show(type, message, options = {}) {
  const id = originalCreate({ message, type, ...options })
  dismissAfter(id, durationSeconds(options))
  return id
}

/** Same API as frappe-ui `toast`, with guaranteed auto-dismiss. */
export const toast = {
  create: (options = {}) => {
    const id = originalCreate(options)
    dismissAfter(id, durationSeconds(options))
    return id
  },
  remove: (...args) => baseToast.remove(...args),
  removeAll: (...args) => baseToast.removeAll(...args),
  promise: (...args) => baseToast.promise(...args),
  success: (message, options = {}) => show('success', message, options),
  error: (message, options = {}) => show('error', message, options),
  warning: (message, options = {}) => show('warning', message, options),
  info: (message, options = {}) => show('info', message, options),
}

/**
 * Patch the host toast object used by Toasts.
 * Also best-effort patch `frappe-ui`'s export for any leftover imports.
 */
export function installToastAutoDismiss() {
  baseToast.success = toast.success
  baseToast.error = toast.error
  baseToast.warning = toast.warning
  baseToast.info = toast.info
  baseToast.create = toast.create
}
