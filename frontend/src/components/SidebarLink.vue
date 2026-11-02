<template>
  <button
    type="button"
    class="mx-2 my-0.5 flex h-7 w-[calc(100%-1rem)] cursor-pointer items-center rounded text-gray-700 duration-300 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
    :class="isActive ? 'bg-white shadow-sm' : 'hover:bg-gray-100'"
    @click="handleClick"
  >
    <div class="flex w-full items-center truncate px-2 py-1">
      <span class="grid flex-shrink-0 place-items-center">
        <FeatherIcon v-if="typeof icon === 'string'" :name="icon" class="size-4 text-gray-700" />
        <component :is="icon" v-else class="size-4 text-gray-700" />
      </span>
      <span class="ml-2 truncate text-sm">{{ label }}</span>
      <slot name="right" />
    </div>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({
  icon: { type: [Object, String], default: 'circle' },
  label: { type: String, default: '' },
  to: { type: String, default: '' },
})

const router = useRouter()
const route = useRoute()

const isActive = computed(() => {
  if (!props.to) return false
  if (props.to === '/') return route.path === '/' || route.path === ''
  return route.path === props.to || route.path.startsWith(`${props.to}/`)
})

function handleClick() {
  if (!props.to) return
  router.push(props.to)
}
</script>
