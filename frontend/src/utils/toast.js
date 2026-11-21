/**
 * LYQD toast helper on frappe-ui 1.x (vue-sonner).
 * Keeps the old call shape: toast.success(message) / toast.error(message).
 */
import { toast as baseToast } from '@/utils/frappeToastHost'

export { ToastProvider } from '@/utils/frappeToastHost'

const DEFAULT_MS = 5000

function durationMs(options = {}) {
  if (options.duration != null && options.duration !== '') {
    const n = Number(options.duration)
    // Legacy LYQD used seconds; sonner uses ms. Treat small numbers as seconds.
    if (!Number.isFinite(n)) return DEFAULT_MS
    return n > 0 && n <= 60 ? n * 1000 : n
  }
  return DEFAULT_MS
}

function withDuration(options = {}) {
  const { duration, ...rest } = options
  return { ...rest, duration: durationMs(options) }
}

function show(type, message, options = {}) {
  const data = withDuration(options)
  if (type === 'success') return baseToast.success(message, data)
  if (type === 'error') return baseToast.error(message, data)
  if (type === 'warning') return baseToast.warning(message, data)
  if (type === 'info') return baseToast.info(message, data)
  return baseToast(message, data)
}

export const toast = {
  /** Legacy frappe-ui 0.1 shape: { message, type, duration? } */
  create: (options = {}) => {
    const { message = '', type, ...rest } = options
    return show(type, message, rest)
  },
  remove: (...args) => baseToast.dismiss?.(...args),
  removeAll: () => baseToast.dismiss?.(),
  promise: (...args) => baseToast.promise(...args),
  success: (message, options = {}) => show('success', message, options),
  error: (message, options = {}) => show('error', message, options),
  warning: (message, options = {}) => show('warning', message, options),
  info: (message, options = {}) => show('info', message, options),
}

/** No-op: sonner dismisses on its own; kept for main.js bootstrap. */
export function installToastAutoDismiss() {}
