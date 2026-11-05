<template>
  <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
    <div class="min-w-0">
      <h1 class="text-xl font-semibold text-gray-900">{{ title }}</h1>
      <p
        v-if="subtitle || $slots.subtitle"
        class="mt-0.5 text-p-base text-gray-600"
      >
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
    </div>
    <div class="flex shrink-0 flex-wrap items-center gap-2">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: String,
  subtitle: String,
})
</script>
