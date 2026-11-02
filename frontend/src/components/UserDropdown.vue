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

const company = useCompanyStore()
const session = useSessionStore()
const router = useRouter()
const logoUrl = '/assets/lyqd/images/lyqd.svg'

const dropdownOptions = computed(() => [
  {
    group: 'Navigate',
    hideLabel: true,
    items: [
      {
        icon: 'grid',
        label: 'Desk',
        onClick: () => {
          window.location.href = '/app'
        },
      },
      {
        icon: 'settings',
        label: 'Settings',
        onClick: () => router.push('/settings'),
      },
    ],
  },
  {
    group: 'Account',
    hideLabel: true,
    items: [
      {
        icon: 'log-out',
        label: 'Log out',
        onClick: () => session.logout.submit(),
      },
    ],
  },
])
</script>
