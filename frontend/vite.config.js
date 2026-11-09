import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { VitePWA } from 'vite-plugin-pwa'

/**
 * frappe-ui Select defaults to item-aligned menus. In dialogs (e.g. Add payment
 * Category with "Other" selected), that opens the list upward. Force popper +
 * bottom so menus open below the trigger when space allows.
 */
function lyqdSelectPopper() {
  return {
    name: 'lyqd-select-popper',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('/frappe-ui/') || !id.endsWith('/Select/Select.vue')) {
        return null
      }
      if (!code.includes('<SelectContent') || code.includes('position="popper"')) {
        return null
      }
      return code.replace(
        '<SelectContent\n        data-slot="content"\n        class="z-[100] origin-[var(--reka-select-content-transform-origin)]"',
        `<SelectContent
        position="popper"
        side="bottom"
        :side-offset="4"
        :avoid-collisions="true"
        data-slot="content"
        class="z-[100] min-w-[var(--reka-select-trigger-width)] origin-[var(--reka-select-content-transform-origin)]"`,
      )
    },
  }
}

/** Calendar events default to click-to-open popovers; LYQD uses hover like plan-list info. */
function lyqdCalendarHoverPopover() {
  return {
    name: 'lyqd-calendar-hover-popover',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('/frappe-ui/') || !id.includes('/Calendar/')) return null
      const isMonth = id.endsWith('/CalendarMonthEvent.vue')
      const isWeek = id.endsWith('/CalendarWeekDayEvent.vue')
      if (!isMonth && !isWeek) return null
      if (code.includes('trigger="hover"')) return null

      let next = code
      if (isMonth) {
        next = next.replace(
          '<Popover placement="left" transition="default"',
          '<Popover trigger="hover" :leave-delay="0.2" placement="left" transition="default"',
        )
        next = next.replace(
          '@click.stop="handleEventClick($event, togglePopover, isOpen)"',
          '@click.stop',
        )
      } else {
        next = next.replace(
          '<Popover\n    :placement="activeView === \'Week\' ? \'left\' : \'center\'"\n    transition="default"',
          '<Popover\n    trigger="hover"\n    :leave-delay="0.2"\n    :placement="activeView === \'Week\' ? \'left\' : \'center\'"\n    transition="default"',
        )
        next = next.replace(
          '@click.prevent="handleEventClick($event, togglePopover)"',
          '@click.prevent.stop',
        )
      }
      return next === code ? null : next
    },
  }
}

export default defineConfig({
  plugins: [
    lyqdSelectPopper(),
    lyqdCalendarHoverPopover(),
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      frontendRoute: '/lyqd',
      buildConfig: {
        outDir: '../lyqd/public/frontend',
        indexHtmlPath: '../lyqd/www/lyqd.html',
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      devOptions: {
        enabled: false,
      },
      workbox: {
        // Avoid workbox+terser "Unexpected early exit" on some Node builds.
        mode: 'development',
        cleanupOutdatedCaches: true,
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webp}'],
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.destination === 'document',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'lyqd-html-cache',
            },
          },
        ],
      },
      // Manifest is served by lyqd.api.spa.get_pwa_manifest (LMS-style), not embedded.
      manifest: false,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      // frappe-ui 0.1.x: toast API is root-exported; Toasts host is not.
      'frappe-ui/toasts': path.resolve(
        __dirname,
        'node_modules/frappe-ui/src/components/Toast/index.ts',
      ),
    },
  },
  build: {
    outDir: '../lyqd/public/frontend',
    emptyOutDir: true,
    target: 'esnext',
    commonjsOptions: {
      include: [/tailwind.config.js/, /node_modules/],
    },
    sourcemap: true,
  },
  optimizeDeps: {
    include: ['feather-icons', 'tailwind.config.js', 'engine.io-client'],
  },
  server: {
    port: 8081,
  },
})
