import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { VitePWA } from 'vite-plugin-pwa'

/**
 * frappe-ui Select defaults to item-aligned menus (opens over the trigger).
 * Force popper mode so menus open below in dialogs.
 */
function lyqdSelectPopper() {
  return {
    name: 'lyqd-select-popper',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('/frappe-ui/') || !id.endsWith('/Select/Select.vue')) {
        return null
      }
      if (!code.includes('usesPopperPosition')) return null
      const next = code.replace(
        /const usesPopperPosition = computed\(\s*\(\)\s*=>\s*[\s\S]*?\)/,
        `const usesPopperPosition = computed(() => true)`,
      )
      return next === code ? null : next
    },
  }
}

/**
 * Reka HoverCard only closes via a grace-area polygon between trigger and
 * content. Large calendar event panels make that hull cover most of the
 * dialog, so the card never dismisses. Start the close timer on trigger
 * leave; content pointerenter still cancels it via onOpen.
 */
function lyqdHoverCardLeaveFix() {
  return {
    name: 'lyqd-hovercard-leave-fix',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('HoverCardTrigger') || id.includes('?')) return null
      if (code.includes('/* lyqd-leave-fix */')) return null
      // Always start close on trigger leave. Content pointerenter cancels via onOpen.
      // Reka's grace-area hull is too large for calendar event panels and never exits.
      const needle =
        'if (!rootContext.isPointerInTransitRef.value && !rootContext.open.value)'
      if (!code.includes(needle)) return null
      const next = code.replace(
        /function handleLeave\(\) \{[\s\S]*?\n\t\t\}\n\t\tfunction handleTouch/,
        `function handleLeave() {\n\t\t\t/* lyqd-leave-fix */\n\t\t\trootContext.onClose();\n\t\t}\n\t\tfunction handleTouch`,
      )
      // Vue SFC uses 2-space indent
      const next2 =
        next === code
          ? code.replace(
              /function handleLeave\(\) \{[\s\S]*?\n\}\n\nfunction handleTouch/,
              `function handleLeave() {\n  /* lyqd-leave-fix */\n  rootContext.onClose()\n}\n\nfunction handleTouch`,
            )
          : next
      if (next2 === code) return null
      return { code: next2, map: null }
    },
  }
}

/**
 * Calendar events: use HoverCard (open/close on hover with leave delay) instead
 * of click Popover. Also stop month/week pills from forcing open stuck true.
 */
function lyqdCalendarHoverPopover() {
  return {
    name: 'lyqd-calendar-hover-popover',
    enforce: 'pre',
    transform(code, id) {
      // Match absolute or bare package ids (e.g. frappe-ui/experimental/...).
      const isFrappeUi = id.includes('frappe-ui/')
      const isCalendar = id.includes('/Calendar/') || id.includes('Calendar/')
      if (!isFrappeUi || !isCalendar) return null

      const isPopoverFile =
        id.includes('/CalendarEventPopover.vue') ||
        id.endsWith('CalendarEventPopover.vue')
      if (isPopoverFile && !id.includes('?')) {
        if (code.includes('/* lyqd-hovercard */')) return null
        let next = code
        next = next.replace(
          "import Popover from '#components/Popover/Popover.vue'",
          "import HoverCard from '#components/HoverCard/HoverCard.vue'",
        )
        next = next.replace(/<Popover\b/g, '<HoverCard')
        next = next.replace(/<\/Popover>/g, '</HoverCard>')
        // Drop controlled :open so HoverCard can close on pointer leave.
        // Still sync open/close up for delete-shortcut registration.
        next = next.replace(
          `:open="open"
    :side="side"
    align="center"
    @update:open="(value) => !value && emit('update:open', false)"
    @open="emit('open')"
    @close="emit('close')"`,
          `:side="side"
    align="center"
    :hover-delay="80"
    :leave-delay="200"
    @update:open="(value) => { emit('update:open', value); value ? emit('open') : emit('close') }"`,
        )
        if (next === code || !next.includes('HoverCard')) return null
        next = next.replace(
          '<script setup lang="ts">',
          '<script setup lang="ts">\n/* lyqd-hovercard */',
        )
        return { code: next, map: null }
      }

      // HoverCard owns open state — don't force-open via click/mouseenter.
      if (
        (id.includes('/CalendarMonthEvent.vue') ||
          id.endsWith('CalendarMonthEvent.vue')) &&
        !id.includes('?')
      ) {
        if (code.includes('data-lyqd-hovercard')) return null
        let next = code.replace(
          /@click\.stop="\s*handleEventClick\(\s*\$event,\s*\(\)\s*=>\s*\(isPopoverOpen\s*=\s*!isPopoverOpen\),\s*isPopoverOpen,\s*\)\s*"/,
          'data-lyqd-hovercard @click.stop',
        )
        next = next
          .replace('@mouseenter="isPopoverOpen = true"\n      @click.stop', 'data-lyqd-hovercard @click.stop')
          .replace(/\s*@mouseenter="isPopoverOpen = true"/g, '')
        return next === code ? null : { code: next, map: null }
      }

      if (
        (id.includes('/CalendarWeekDayEvent.vue') ||
          id.endsWith('CalendarWeekDayEvent.vue')) &&
        !id.includes('?')
      ) {
        if (code.includes('data-lyqd-hovercard')) return null
        let next = code.replace(
          /@click\.stop\.prevent="\s*handleEventClick\(\$event,\s*\(\)\s*=>\s*\(isPopoverOpen\s*=\s*!isPopoverOpen\)\)\s*"/,
          'data-lyqd-hovercard @click.stop.prevent',
        )
        next = next
          .replace(/\n\s*@mouseenter="isPopoverOpen = true"/g, '')
          .replace(/\n\s*@mouseenter\.self="isPopoverOpen = true"/g, '')
        if (next !== code) {
          next = next.replace(
            '<script setup lang="ts">',
            '<script setup lang="ts">\n// data-lyqd-hovercard',
          )
        }
        return next === code ? null : { code: next, map: null }
      }

      return null
    },
  }
}

export default defineConfig({
  plugins: [
    lyqdSelectPopper(),
    lyqdHoverCardLeaveFix(),
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
      manifest: false,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
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
