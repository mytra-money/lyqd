<template>
  <div class="flex h-[100dvh] w-screen overflow-hidden">
    <!-- Desktop sidebar -->
    <aside
      class="hidden h-full w-[220px] shrink-0 flex-col border-r border-gray-200 bg-gray-50 md:flex"
    >
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

    <!-- Mobile drawer -->
    <Teleport to="body">
      <div v-if="mobileNavOpen" class="fixed inset-0 z-40 md:hidden">
        <div
          class="absolute inset-0 bg-gray-900/40"
          aria-hidden="true"
          @click="mobileNavOpen = false"
        />
        <aside
          class="absolute inset-y-0 left-0 flex w-[min(18rem,86vw)] flex-col border-r border-gray-200 bg-gray-50 shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
        >
          <div class="flex items-center justify-between gap-2 border-b border-gray-200 p-2">
            <UserDropdown />
            <button
              type="button"
              class="rounded-md p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-800"
              aria-label="Close menu"
              @click="mobileNavOpen = false"
            >
              <FeatherIcon name="x" class="h-4 w-4" />
            </button>
          </div>
          <div class="flex-1 overflow-y-auto pb-6 pt-2">
            <div class="mb-1 px-4 text-xs font-medium text-gray-500">Cash & liquidity</div>
            <nav class="flex flex-col">
              <SidebarLink
                v-for="item in primaryNav"
                :key="`m-${item.to}`"
                :to="item.to"
                :label="item.label"
                :icon="item.icon"
              />
            </nav>
            <div class="mb-1 mt-4 px-4 text-xs font-medium text-gray-500">More</div>
            <nav class="flex flex-col">
              <SidebarLink
                v-for="item in moreNav"
                :key="`m-${item.to}`"
                :to="item.to"
                :label="item.label"
                :icon="item.icon"
              />
            </nav>
          </div>
        </aside>
      </div>
    </Teleport>

    <div class="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
      <header
        class="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-gray-200 px-3 pt-[env(safe-area-inset-top)] md:gap-3 md:px-6"
      >
        <div class="flex shrink-0 items-center gap-1.5 md:hidden">
          <button
            type="button"
            class="rounded-md p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            aria-label="Open menu"
            @click="mobileNavOpen = true"
          >
            <FeatherIcon name="menu" class="h-4 w-4" />
          </button>
          <div class="text-sm font-semibold text-gray-900">LYQD</div>
        </div>
        <div class="hidden min-w-0 flex-1 items-center gap-2 text-sm text-gray-600 md:flex">
          <span class="truncate">{{ pageHint }}</span>
        </div>
        <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <span
            v-if="company.inBeta"
            class="shrink-0 rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white"
          >
            Beta
          </span>
          <HorizonPicker v-if="showHorizon" v-model="horizon" />
          <button
            v-if="showHorizon"
            type="button"
            class="inline-flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            title="Plan calendar"
            aria-label="Open plan calendar"
            @click="openPlanCalendar"
          >
            <FeatherIcon name="calendar" class="h-4 w-4" />
          </button>
          <FormControl
            type="select"
            size="sm"
            class="min-w-[7.5rem] max-w-[11rem] sm:max-w-none sm:w-40 md:w-48"
            :model-value="company.current || ''"
            :options="companyOptions"
            :title="company.current || ''"
            @update:model-value="onCompanySelect"
          />
        </div>
      </header>

      <main
        class="flex-1 overflow-auto px-3 py-4 pb-[calc(4.25rem+env(safe-area-inset-bottom))] md:px-6 md:py-5 md:pb-5"
      >
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

      <!-- Mobile bottom tabs -->
      <nav
        class="fixed inset-x-0 bottom-0 z-30 flex border-t border-gray-200 bg-white/95 backdrop-blur md:hidden"
        style="padding-bottom: env(safe-area-inset-bottom)"
        aria-label="Primary"
      >
        <button
          v-for="item in mobileTabs"
          :key="item.to || item.id"
          type="button"
          class="flex flex-1 flex-col items-center gap-0.5 px-1 py-2 text-[10px] font-medium"
          :class="
            isTabActive(item)
              ? 'text-gray-900'
              : 'text-gray-500 hover:text-gray-800'
          "
          @click="onMobileTab(item)"
        >
          <FeatherIcon :name="item.icon" class="h-4 w-4" />
          <span class="truncate">{{ item.short || item.label }}</span>
        </button>
      </nav>
    </div>

    <AddCompanyDialog
      v-model="company.showAddCompany"
      :required="company.needsOnboarding"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStorage } from '@vueuse/core'
import SidebarLink from '@/components/SidebarLink.vue'
import UserDropdown from '@/components/UserDropdown.vue'
import AddCompanyDialog from '@/components/AddCompanyDialog.vue'
import HorizonPicker from '@/components/HorizonPicker.vue'
import { mobileNavOpen } from '@/composables/useMobile'
import { useHorizon } from '@/composables/useHorizon'
import { useCompanyStore } from '@/stores/company'

const company = useCompanyStore()
const route = useRoute()
const router = useRouter()
const showMore = useStorage('lyqd_show_more_nav', false)
const { horizon } = useHorizon()

/** Horizon affects Cash position, Free cash, and Proposal. */
const showHorizon = computed(() => {
  const p = route.path
  return (
    p === '/' ||
    p === '' ||
    p === '/surplus' ||
    p === '/proposal' ||
    p.startsWith('/runs')
  )
})

function openPlanCalendar() {
  router.push({ path: '/', query: { view: 'calendar' } })
}

const primaryNav = [
  { to: '/', label: 'Cash position', icon: 'home', short: 'Cash' },
  { to: '/upcoming', label: 'Commitments', icon: 'calendar', short: 'Plan' },
  { to: '/surplus', label: 'Free cash', icon: 'pie-chart', short: 'Free' },
  { to: '/proposal', label: 'Proposal', icon: 'file-text', short: 'Proposal' },
  { to: '/holdings', label: 'Portfolio', icon: 'briefcase', short: 'Portfolio' },
]

const moreNav = [
  { to: '/instructions', label: 'Instructions', icon: 'send' },
  { to: '/cash', label: 'Bank balances', icon: 'credit-card' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

/** Bottom bar: four primaries + More (opens drawer). Portfolio lives under More on phone. */
const mobileTabs = [
  primaryNav[0],
  primaryNav[1],
  primaryNav[2],
  primaryNav[3],
  { id: 'more', label: 'More', short: 'More', icon: 'menu', to: null },
]

const companyOptions = computed(() => {
  const rows = (company.companies || []).map((c) => ({ label: c, value: c }))
  rows.push({ label: '+ Add company…', value: '__add__' })
  return rows
})

function onCompanySelect(v) {
  company.setCompany(v)
}

function isTabActive(item) {
  if (item.id === 'more') {
    return moreNav.some(
      (n) => route.path === n.to || route.path.startsWith(`${n.to}/`),
    ) || route.path === '/holdings' || route.path.startsWith('/holdings/')
  }
  if (!item.to) return false
  if (item.to === '/') return route.path === '/' || route.path === ''
  return route.path === item.to || route.path.startsWith(`${item.to}/`)
}

function onMobileTab(item) {
  if (item.id === 'more') {
    mobileNavOpen.value = true
    return
  }
  if (item.to) router.push(item.to)
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
