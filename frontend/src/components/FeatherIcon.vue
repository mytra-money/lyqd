<script setup>
/**
 * Local stand-in for frappe-ui 0.1 FeatherIcon (removed in 1.x / lucide).
 * Keeps existing `name` + class usages working via the feather-icons package.
 */
import { computed, useAttrs } from 'vue'
import feather from 'feather-icons'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  name: { type: String, required: true },
})

const attrs = useAttrs()

const svg = computed(() => {
  const icon = feather.icons[props.name]
  if (!icon) return ''
  return icon.toSvg({
    width: '100%',
    height: '100%',
    'stroke-width': 2,
    'aria-hidden': 'true',
  })
})
</script>

<template>
  <span
    class="inline-flex size-4 shrink-0 items-center justify-center [&>svg]:block [&>svg]:h-full [&>svg]:w-full"
    v-bind="attrs"
    aria-hidden="true"
    v-html="svg"
  />
</template>
