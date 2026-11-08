/**
 * frappe-ui toast + reka-ui ToastRoot can stay open when the viewport
 * pause/resume cycle sticks (hover near the toast corner, window blur).
 * Schedule an explicit remove so success/error toasts always dismiss.
 */
import { toast as baseToast } from 'frappe-ui'

const DEFAULT_SECONDS = 5

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

function wrap(method) {
  return (message, options = {}) => {
    const id = method.call(baseToast, message, options)
    const seconds =
      options.duration != null && options.duration !== ''
        ? Number(options.duration)
        : DEFAULT_SECONDS
    dismissAfter(id, Number.isFinite(seconds) ? seconds : DEFAULT_SECONDS)
    return id
  }
}

/** Same API as frappe-ui `toast`, with guaranteed auto-dismiss. */
export const toast = {
  create: (options = {}) => {
    const id = baseToast.create(options)
    const seconds =
      options.duration != null && options.duration !== ''
        ? Number(options.duration)
        : DEFAULT_SECONDS
    dismissAfter(id, Number.isFinite(seconds) ? seconds : DEFAULT_SECONDS)
    return id
  },
  remove: (...args) => baseToast.remove(...args),
  removeAll: (...args) => baseToast.removeAll(...args),
  promise: (...args) => baseToast.promise(...args),
  success: wrap(baseToast.success),
  error: wrap(baseToast.error),
  warning: wrap(baseToast.warning),
  info: wrap(baseToast.info),
}

/** Patch the shared frappe-ui toast singleton (covers `import { toast } from 'frappe-ui'`). */
export function installToastAutoDismiss() {
  baseToast.success = toast.success
  baseToast.error = toast.error
  baseToast.warning = toast.warning
  baseToast.info = toast.info
  baseToast.create = toast.create
}
