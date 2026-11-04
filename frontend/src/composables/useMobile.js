import { useMediaQuery } from '@vueuse/core'
import { ref } from 'vue'

/** Match Tailwind `md` breakpoint used by the desktop sidebar. */
export const isMobileView = useMediaQuery('(max-width: 767px)')

/** Drawer open state for mobile navigation. */
export const mobileNavOpen = ref(false)
