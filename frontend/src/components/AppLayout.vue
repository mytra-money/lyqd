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
          <span>{{ pageHint }}</span>
        </div>
        <div class="flex items-center gap-2">
          <FormControl
            type="select"
            size="sm"
            class="w-52"
            :model-value="company.current || ''"
            :options="companyOptions"
            @update:model-value="onCompanySelect"
          />
        </div>
      </header>

      <main class="flex-1 overflow-auto px-4 py-5 md:px-6">
        <div
          v-if="company.needsOnboarding"
          class="mx-auto max-w-lg rounded-lg border border-amber-200 bg-amber-50 px-4 py-6 text-center"
        >
          <h2 class="text-base font-semibold text-amber-950">Create your company</h2>
          <Button class="mt-4" variant="solid" @click="company.openAddCompany()">
            Create company
          </Button>
        </div>
        <slot v-else />
      </main>
    </div>

    <AddCompanyDialog
      v-model="company.showAddCompany"
      :required="company.needsOnboarding"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useStorage } from '@vueuse/core'
import SidebarLink from '@/components/SidebarLink.vue'
import UserDropdown from '@/components/UserDropdown.vue'
import AddCompanyDialog from '@/components/AddCompanyDialog.vue'
import { useCompanyStore } from '@/stores/company'

const company = useCompanyStore()
const route = useRoute()
const showMore = useStorage('lyqd_show_more_nav', false)

const primaryNav = [
  { to: '/', label: 'Cash position', icon: 'home' },
  { to: '/upcoming', label: 'Commitments', icon: 'calendar' },
  { to: '/surplus', label: 'Free cash', icon: 'pie-chart' },
  { to: '/proposal', label: 'Proposal', icon: 'file-text' },
  { to: '/holdings', label: 'Portfolio', icon: 'briefcase' },
]

const moreNav = [
  { to: '/instructions', label: 'Instructions', icon: 'send' },
  { to: '/cash', label: 'Bank balances', icon: 'credit-card' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

const companyOptions = computed(() => {
  const rows = (company.companies || []).map((c) => ({ label: c, value: c }))
  rows.push({ label: '+ Add company…', value: '__add__' })
  return rows
})

function onCompanySelect(v) {
  company.setCompany(v)
}

const pageHint = computed(() => {
  const map = {
    '/': 'Morning cash position · liquidity · invest / redeem',
    '/upcoming': 'Near-term payment commitments (incl. overdue)',
    '/surplus': 'Free cash = position − commitments − policy reserves',
    '/proposal': 'Invest or redeem proposals from free cash',
    '/holdings': 'Liquid fund portfolio',
    '/settings': 'Banks, policy, ERPNext integration',
  }
  if (route.path.startsWith('/runs')) return 'Saved free-cash calculation snapshot'
  return map[route.path] || 'Corporate surplus cash'
})
</script>
