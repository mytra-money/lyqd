<template>
  <div class="h-full min-h-[100dvh]">
    <AppLayout v-if="ready">
      <router-view v-slot="{ Component }">
        <KeepAlive :include="keptAlivePages">
          <component :is="Component" />
        </KeepAlive>
      </router-view>
    </AppLayout>
    <div v-else class="flex h-[100dvh] items-center justify-center text-gray-500">
      Loading LYQD…
    </div>
    <InstallPrompt v-if="ready" />
    <!-- Position host like CRM; Toasts is not re-exported from frappe-ui package root. -->
    <div
      class="pointer-events-none fixed bottom-4 right-4 z-[2147483647] flex flex-col items-end gap-2"
    >
      <Toasts />
    </div>
  </div>
</template>

<script setup>
import { KeepAlive, onMounted, ref } from 'vue'
import { Toasts } from 'frappe-ui/toasts'
import AppLayout from '@/components/AppLayout.vue'
import InstallPrompt from '@/components/InstallPrompt.vue'
import { useCompanyStore } from '@/stores/company'

const ready = ref(false)
const company = useCompanyStore()
/** Keep hot treasury pages mounted so navigation does not remount + refetch. */
const keptAlivePages = ['Dashboard', 'Upcoming', 'Cash', 'Surplus']

onMounted(async () => {
  await company.bootstrap()
  ready.value = true
})
</script>
