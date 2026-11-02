<template>
  <div class="flex h-screen w-screen overflow-hidden">
    <aside class="hidden h-full w-[220px] shrink-0 flex-col border-r border-gray-200 bg-gray-50 md:flex">
      <div class="p-2">
        <UserDropdown />
      </div>

      <div class="flex-1 overflow-y-auto pb-3">
        <div class="mb-1 px-4 pt-1 text-xs font-medium text-gray-500">Cash & liquidity</div>
        <nav class="flex flex-col">
          <SidebarLink
            v-for="item in primaryNav"
            :key="item.to"
            :to="item.to"
            :label="item.label"
            :icon="item.icon"
          />
        </nav>

        <button
          type="button"
          class="mt-4 flex w-full cursor-pointer items-center gap-1.5 px-3 text-xs font-medium text-gray-500 hover:text-gray-700"
          @click="showMore = !showMore"
        >
          <FeatherIcon
            name="chevron-right"
            class="h-3.5 w-3.5 transition-transform"
            :class="{ 'rotate-90': showMore }"
          />
          More
        </button>
        <nav v-if="showMore" class="mt-1 flex flex-col">
          <SidebarLink
            v-for="item in moreNav"
            :key="item.to"
            :to="item.to"
            :label="item.label"
            :icon="item.icon"
          />
        </nav>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
      <header
        class="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-gray-200 px-4 md:px-6"
      >
        <div class="min-w-0 md:hidden">
          <div class="text-sm font-medium text-gray-900">LYQD</div>
        </div>
        <div class="hidden items-center gap-2 text-sm text-gray-600 md:flex">
          <Badge theme="orange" variant="subtle">Beta</Badge>
          <span>{{ pageHint }}</span>
        </div>
        <div class="flex items-center gap-2">
          <FormControl
            type="select"
            size="sm"
            class="w-48"
            :model-value="company.current"
            :options="companyOptions"
            @update:model-value="(v) => company.setCompany(v)"
          />
        </div>
      </header>

      <main class="flex-1 overflow-auto px-4 py-5 md:px-6">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useStorage } from '@vueuse/core'
import SidebarLink from '@/components/SidebarLink.vue'
import UserDropdown from '@/components/UserDropdown.vue'
import { useCompanyStore } from '@/stores/company'

const company = useCompanyStore()
const route = useRoute()
const showMore = useStorage('lyqd_show_more_nav', false)

const primaryNav = [
  { to: '/', label: 'Cash position', icon: 'home' },
  { to: '/upcoming', label: 'Commitments', icon: 'calendar' },
  { to: '/surplus', label: 'Free cash', icon: 'pie-chart' },
  { to: '/invest', label: 'Invest', icon: 'trending-up' },
  { to: '/holdings', label: 'Portfolio', icon: 'briefcase' },
]

const moreNav = [
  { to: '/instructions', label: 'Instructions', icon: 'send' },
  { to: '/schemes', label: 'Schemes', icon: 'layers' },
  { to: '/cash', label: 'Bank balances', icon: 'credit-card' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

const companyOptions = computed(() =>
  (company.companies || []).map((c) => ({ label: c, value: c })),
)

const pageHint = computed(() => {
  const map = {
    '/': 'Morning cash position · liquidity · invest / redeem',
    '/upcoming': 'Near-term payment commitments (incl. overdue)',
    '/surplus': 'Free cash = position − commitments − policy reserves',
    '/invest': 'Investment requests from free cash',
    '/holdings': 'Liquid fund portfolio',
    '/settings': 'Banks, policy, ERPNext integration',
  }
  if (route.path.startsWith('/runs')) return 'Saved free-cash calculation snapshot'
  return map[route.path] || 'Corporate surplus cash · beta'
})
</script>
