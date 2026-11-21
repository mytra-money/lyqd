<template>
  <Dropdown :options="dropdownOptions">
    <template #default="{ open }">
      <button
        type="button"
        class="flex h-12 w-full items-center rounded-md px-2 py-2 text-left duration-300 ease-in-out"
        :class="open ? 'bg-white shadow-sm' : 'hover:bg-gray-200'"
      >
        <img
          :src="logoUrl"
          alt="LYQD"
          class="size-7 shrink-0 rounded-lg"
        />
        <div class="ml-2 min-w-0 flex-1">
          <div class="truncate text-sm font-medium leading-none text-gray-900">LYQD</div>
          <div class="mt-1 truncate text-xs leading-none text-gray-600">
            {{ company.userFullname || company.user }}
          </div>
        </div>
        <FeatherIcon name="chevron-down" class="ml-1 size-4 shrink-0 text-gray-600" />
      </button>
    </template>
  </Dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Dropdown } from 'frappe-ui'
import { useCompanyStore } from '@/stores/company'
import { useSessionStore } from '@/stores/session'

const DOCS_URL = 'https://docs.mytra.money/lyqd'

const company = useCompanyStore()
const session = useSessionStore()
const router = useRouter()
const logoUrl = '/assets/lyqd/images/lyqd.svg?v=3'

const dropdownOptions = computed(() => {
  const navigateItems = []
  if (company.hasDeskAccess) {
    navigateItems.push({
      icon: 'lucide-layout-grid',
      label: 'Desk',
      onClick: () => {
        window.location.href = '/app'
      },
    })
  }
  navigateItems.push(
    {
      icon: 'lucide-book-open',
      label: 'View Documentation',
      onClick: () => {
        window.open(DOCS_URL, '_blank', 'noopener,noreferrer')
      },
    },
    {
      icon: 'lucide-settings',
      label: 'Settings',
      onClick: () => router.push('/settings'),
    },
  )

  return [
    {
      group: 'Navigate',
      hideLabel: true,
      options: navigateItems,
    },
    {
      group: 'Account',
      hideLabel: true,
      options: [
        {
          icon: 'lucide-log-out',
          label: 'Log out',
          onClick: () => session.logout.submit(),
        },
      ],
    },
  ]
})
</script>
