<template>
  <div class="h-full min-h-screen">
    <AppLayout v-if="ready">
      <router-view v-slot="{ Component }">
        <KeepAlive :include="keptAlivePages">
          <component :is="Component" />
        </KeepAlive>
      </router-view>
    </AppLayout>
    <div v-else class="flex h-screen items-center justify-center text-gray-500">
      Loading LYQD…
    </div>
    <ToastHost />
  </div>
</template>

<script setup>
import { KeepAlive, onMounted, ref } from 'vue'
import AppLayout from '@/components/AppLayout.vue'
import ToastHost from '@/components/ToastHost.vue'
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
