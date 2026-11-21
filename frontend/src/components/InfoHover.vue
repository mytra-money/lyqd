<script setup>
/**
 * Hover info tip (frappe-ui 1.x HoverCard).
 * Replaces the old Popover `#target` / `#body-main` + `trigger="hover"` pattern.
 */
import { HoverCard } from 'frappe-ui'

defineProps({
  /** Popover side: top | right | bottom | left */
  side: { type: String, default: 'bottom' },
  /** Alignment along the side: start | center | end */
  align: { type: String, default: 'start' },
  leaveDelay: { type: Number, default: 120 },
  hoverDelay: { type: Number, default: 80 },
})
</script>

<template>
  <HoverCard
    :side="side"
    :align="align"
    :leave-delay="leaveDelay"
    :hover-delay="hoverDelay"
  >
    <template #trigger>
      <button
        type="button"
        class="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        aria-label="More details"
        @click.stop.prevent
      >
        <FeatherIcon name="info" class="h-3.5 w-3.5" />
      </button>
    </template>
    <template #default="{ close }">
      <slot :close="close" />
    </template>
  </HoverCard>
</template>
