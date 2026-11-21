<template>
  <!-- frappe-ui 1.x: vue-sonner Toaster -->
  <ToastProvider />
  <slot />
</template>

<script setup>
import { ToastProvider } from '@/utils/toast'
</script>
