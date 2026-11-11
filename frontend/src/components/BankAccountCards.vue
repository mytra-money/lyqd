<template>
  <div>
    <EmptyState
      v-if="!(accounts || []).length"
      variant="bank"
      :title="emptyTitle"
      :description="emptyHint"
    >
      <template #actions>
        <Button v-if="showAdd" variant="solid" size="sm" @click="$emit('add')">
          Add bank account
        </Button>
        <Button v-if="showDesk" variant="outline" size="sm" @click="openDesk">
          {{ deskLabel }}
        </Button>
      </template>
    </EmptyState>

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

        <div class="mt-1 line-clamp-1 text-xs text-gray-500">
          <template v-if="ba.bank">{{ ba.bank }}</template>
          <template v-if="ba.bank && ba.bank_account_no"> · </template>
          <template v-if="ba.bank_account_no">{{ ba.bank_account_no }}</template>
        </div>

        <div
          v-if="ba.balance != null"
          class="mt-3 border-t border-gray-100 pt-2"
        >
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-xs text-gray-500">
              {{ balanceCaption(ba) }}
            </span>
            <span
              class="text-sm font-semibold tabular-nums"
              :class="Number(ba.balance) < 0 ? 'text-red-700' : 'text-gray-900'"
            >
              {{ formatINR(ba.balance) }}
            </span>
          </div>
          <div
            v-if="ba.balance_date"
            class="mt-0.5 text-xs text-gray-500"
          >
            As of {{ ba.balance_date }}
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
import EmptyState from '@/components/EmptyState.vue'
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
      'Add a company bank account so statement balances can feed free cash.',
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

function isCreditFacility(accountType) {
  const t = String(accountType || '')
    .trim()
    .toLowerCase()
  return t === 'cash credit' || t === 'overdraft' || t === 'cc' || t === 'od'
}

function balanceCaption(ba) {
  if (isCreditFacility(ba.account_type) && Number(ba.balance) < 0) return 'Drawn'
  if (isCreditFacility(ba.account_type)) return ba.source || 'Balance'
  return ba.source || 'Balance'
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
