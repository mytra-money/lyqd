<template>
  <div class="pointer-events-none fixed bottom-4 right-4 z-[2147483647] flex flex-col items-end gap-2">
    <Toasts />
  </div>
</template>

<script setup>
// Not re-exported from frappe-ui package root in this version
import { Toasts } from '../../node_modules/frappe-ui/src/components/Toast/index.ts'
</script>
