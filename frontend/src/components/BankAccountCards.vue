<template>
  <div>
    <div
      v-if="!(accounts || []).length"
      class="flex flex-col items-center justify-center rounded-md border border-dashed border-gray-300 bg-white px-6 py-10 text-center"
    >
      <div
        class="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 text-gray-600"
      >
        <FeatherIcon name="credit-card" class="h-5 w-5" />
      </div>
      <div class="text-sm font-medium text-gray-900">{{ emptyTitle }}</div>
      <p class="mt-1 max-w-sm text-p-base text-gray-600">
        {{ emptyHint }}
      </p>
      <div class="mt-4 flex flex-wrap justify-center gap-2">
        <Button v-if="showAdd" variant="solid" @click="$emit('add')">Add bank account</Button>
        <Button v-if="showDesk" variant="outline" @click="openDesk">{{ deskLabel }}</Button>
      </div>
    </div>

    <div v-else class="flex gap-3 overflow-x-auto pb-1">
      <button
        v-for="ba in accounts"
        :key="ba.name"
        type="button"
        class="w-60 shrink-0 rounded-md border p-3 text-left transition-colors"
        :class="
          isSelected(ba.name)
            ? 'border-gray-900 bg-gray-50'
            : 'border-gray-200 bg-white hover:bg-gray-50'
        "
        @click="$emit('toggle', ba)"
      >
        <div class="mb-2 flex items-center gap-2">
          <div
            class="flex h-8 w-8 items-center justify-center rounded bg-gray-900 text-xs font-semibold text-white"
          >
            {{ initials(ba) }}
          </div>
          <Badge v-if="ba.is_default" theme="blue" variant="subtle">Default</Badge>
          <Badge
            v-if="selectable && isSelected(ba.name)"
            theme="green"
            variant="subtle"
          >
            In surplus
          </Badge>
        </div>

        <div class="flex items-center gap-2">
          <span class="line-clamp-1 text-sm font-medium text-gray-900">
            {{ ba.account_name || ba.name }}
          </span>
          <Badge v-if="ba.account_type" theme="gray" variant="subtle">
            {{ String(ba.account_type).slice(0, 24) }}
          </Badge>
        </div>

        <div class="mt-1 line-clamp-1 text-sm text-gray-600" :title="ba.account || ''">
          {{ ba.account || 'No GL linked' }}
        </div>
        <div class="mt-0.5 line-clamp-1 text-xs text-gray-500">
          {{ ba.bank || 'Bank' }}
          <span v-if="ba.bank_account_no">· {{ ba.bank_account_no }}</span>
        </div>

        <div
          v-if="ba.balance != null"
          class="mt-3 border-t border-gray-100 pt-2"
        >
          <div class="flex items-baseline justify-between">
            <span class="text-xs text-gray-500">{{ ba.source || 'Balance' }}</span>
            <span class="text-sm font-semibold tabular-nums text-gray-900">
              {{ formatINR(ba.balance) }}
            </span>
          </div>
          <div
            v-if="ba.balance_date"
            class="mt-0.5 text-xs"
            :class="'text-gray-500'"
          >
            As of {{ ba.balance_date }}
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { formatINR } from '@/utils/format'
import { useCompanyStore } from '@/stores/company'

const props = defineProps({
  accounts: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
  selectable: { type: Boolean, default: false },
  showAdd: { type: Boolean, default: true },
  emptyTitle: { type: String, default: 'No bank accounts found' },
  emptyHint: {
    type: String,
    default:
      'You have not added any company bank accounts yet. LYQD creates an ERPNext Chart of Accounts entry and a Bank Account (same as Banking expects).',
  },
  deskUrl: { type: String, default: null },
  deskLabel: { type: String, default: 'Open in Desk' },
  showDesk: { type: Boolean, default: true },
})

defineEmits(['toggle', 'add'])

const company = useCompanyStore()

function isSelected(name) {
  if (!props.selectable) return false
  // Empty selection = all company accounts included in surplus
  if (!(props.selected || []).length) return true
  return props.selected.includes(name)
}

function initials(ba) {
  const raw = (ba.bank || ba.account_name || ba.name || 'B').trim()
  return raw.slice(0, 2).toUpperCase()
}

function openDesk() {
  if (props.deskUrl) {
    window.open(props.deskUrl, '_blank', 'noopener')
    return
  }
  const c = encodeURIComponent(company.current || '')
  window.location.href = `/app/bank-account?company=${c}`
}
</script>
