/**
 * Single module graph entry for frappe-ui toast state + Toasts renderer.
 * Importing toast and Toasts through different package paths can duplicate
 * toastsState in the Vite/Rollup bundle (creates succeed, viewport stays empty).
 */
export { toast, Toasts } from '../../node_modules/frappe-ui/src/components/Toast/index.ts'
