<template>
  <!--
    Thin host around reka-ui + frappe-ui Toasts.
    Toasts must come from @/utils/toast so it shares state with toast.create.
  -->
  <ToastProvider :duration="5000" swipe-direction="down">
    <slot />
    <Toasts />
    <ToastViewport
      class="pointer-events-none fixed bottom-0 right-0 z-[2147483647] flex w-auto max-w-full flex-col items-end gap-[10px] p-5 outline-none"
    />
  </ToastProvider>
</template>

<script setup>
import { ToastProvider, ToastViewport } from 'reka-ui'
import { Toasts } from '@/utils/toast'
</script>
