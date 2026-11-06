<template>
  <li>
    <div
      class="flex items-start gap-2 px-3 py-3 sm:gap-3 sm:px-4"
      :class="hoverable ? 'hover:bg-gray-50/80 sm:items-center' : ''"
    >
      <div
        class="flex h-6 w-6 shrink-0 items-center justify-center"
        :class="hoverable ? 'pt-0.5 sm:pt-0' : 'mt-0.5'"
      >
        <button
          v-if="row._childCount"
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-800"
          :aria-expanded="expanded"
          :aria-label="expanded ? 'Collapse group' : 'Expand group'"
          @click="emit('toggle-group')"
        >
          <FeatherIcon
            :name="expanded ? 'chevron-down' : 'chevron-right'"
            class="h-3.5 w-3.5"
          />
        </button>
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-1">
          <span class="min-w-0 truncate text-sm font-medium leading-5 text-gray-900">
            {{ displayTitle }}
          </span>
          <span
            v-if="row._childCount"
            class="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600"
          >
            {{ row._has_splits ? 'Split' : 'Group' }} · {{ groupSize }}
          </span>
          <Popover
            class="shrink-0 items-center"
            trigger="hover"
            placement="bottom-end"
            :leave-delay="0.12"
          >
            <template #target>
              <button
                type="button"
                class="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                aria-label="More details"
                @click.stop.prevent
              >
                <FeatherIcon name="info" class="h-3.5 w-3.5" />
              </button>
            </template>
            <template #body-main="{ close }">
              <div class="w-64 max-w-[85vw] p-3 text-left">
                <div class="mb-2 text-sm font-semibold text-gray-900">{{ row.title }}</div>
                <dl class="space-y-1.5 text-xs text-gray-600">
                  <div
                    v-for="line in detailLines"
                    :key="line.label"
                    class="flex justify-between gap-3"
                  >
                    <dt class="shrink-0 text-gray-400">{{ line.label }}</dt>
                    <dd class="min-w-0 text-right font-medium text-gray-800">{{ line.value }}</dd>
                  </div>
                </dl>
                <div
                  v-if="canRefresh || canFreeze || canSplit"
                  class="mt-3 flex flex-wrap gap-2 border-t border-gray-100 pt-3"
                >
                  <Button
                    v-if="canRefresh"
                    size="sm"
                    variant="outline"
                    :loading="refreshing"
                    @click="emit('refresh'); close()"
                  >
                    Refresh books
                  </Button>
                  <Button
                    v-if="canSplit"
                    size="sm"
                    variant="outline"
                    @click="emit('split'); close()"
                  >
                    {{ splitLabel }}…
                  </Button>
                  <Button
                    v-if="canFreeze"
                    size="sm"
                    variant="outline"
                    :loading="freezing"
                    @click="
                      row.balance_as_of ? emit('clear-freeze') : emit('freeze');
                      close()
                    "
                  >
                    {{ row.balance_as_of ? 'Unfreeze' : 'Freeze…' }}
                  </Button>
                </div>
              </div>
            </template>
          </Popover>
        </div>

        <div class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
          <span
            :class="
              row.status !== 'Paid' && isOverdue(row.due_date, asOf)
                ? 'font-medium text-red-600'
                : ''
            "
          >
            {{ dueLabel(row.due_date, asOf) }}
          </span>
          <span
            v-if="isInflowEffect(row.cash_effect)"
            class="rounded px-1 py-px text-[10px] font-medium leading-4 text-green-800 bg-green-50"
          >
            {{ row.cash_effect === 'Setoff' ? 'Setoff' : 'Inflow' }}
          </span>
          <span
            v-else
            class="rounded px-1 py-px text-[10px] font-medium leading-4 text-red-700 bg-red-50"
          >
            Outflow
          </span>
          <span
            v-if="row.balance_as_of"
            class="rounded bg-amber-50 px-1 py-px text-[10px] font-medium leading-4 text-amber-900"
          >
            {{ row._has_splits ? 'Split as of' : 'As of' }}
            {{ formatDate(row.balance_as_of) }}
          </span>
        </div>
      </div>

      <div class="w-[5.75rem] shrink-0 text-right sm:w-auto sm:min-w-[6.5rem]">
        <div
          v-if="row._childCount && row._groupNet != null"
          class="tabular-nums font-semibold text-gray-900"
          :class="hoverable ? 'text-base' : 'text-sm'"
        >
          {{ formatINR(row._groupNet) }}
        </div>
        <div
          v-else
          class="tabular-nums text-sm font-semibold"
          :class="isInflowEffect(row.cash_effect) ? 'text-green-800' : 'text-gray-900'"
        >
          {{ isInflowEffect(row.cash_effect) ? '−' : '' }}{{ formatINR(amount) }}
        </div>
        <div class="mt-1 flex flex-wrap items-center justify-end gap-0.5 sm:mt-1.5">
          <!-- Desktop: refresh / freeze on the row; PWA: same actions live in ⓘ -->
          <template v-if="!isMobileView">
            <button
              v-if="canRefresh"
              type="button"
              class="inline-flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50"
              :disabled="refreshing"
              :title="
                row.balance_as_of
                  ? 'Refresh GL as of ' + formatDate(row.balance_as_of)
                  : 'Refresh from live books'
              "
              :aria-label="
                row.balance_as_of
                  ? 'Refresh GL as of ' + formatDate(row.balance_as_of)
                  : 'Refresh from live books'
              "
              @click="emit('refresh')"
            >
              <FeatherIcon
                name="refresh-cw"
                class="h-3.5 w-3.5"
                :class="refreshing ? 'animate-spin' : ''"
              />
            </button>
            <Button
              v-if="canSplit"
              size="sm"
              variant="ghost"
              class="!h-auto !px-1.5 !py-0.5 !text-xs !font-normal !text-gray-600 hover:!bg-gray-100"
              :title="splitLabel + ' into dated rows'"
              @click="emit('split')"
            >
              {{ splitLabel }}
            </Button>
            <Button
              v-if="canFreeze"
              size="sm"
              variant="ghost"
              class="!h-auto !px-1.5 !py-0.5 !text-xs !font-normal !text-amber-800 hover:!bg-amber-50"
              :loading="freezing"
              :title="row.balance_as_of ? 'Unfreeze · use live GL' : 'Freeze GL as of a date'"
              @click="row.balance_as_of ? emit('clear-freeze') : emit('freeze')"
            >
              {{ row.balance_as_of ? 'Unfreeze' : 'Freeze…' }}
            </Button>
          </template>
          <button
            v-if="canMarkPaid"
            type="button"
            class="inline-flex h-7 items-center gap-1 rounded px-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50"
            :disabled="marking"
            :title="
              row.is_recurring
                ? `Record ${(row.frequency || 'Monthly').toLowerCase()} · advance next due`
                : 'Mark paid'
            "
            :aria-label="
              row.is_recurring
                ? `Record ${(row.frequency || 'Monthly').toLowerCase()}`
                : 'Mark paid'
            "
            @click="emit('mark-paid')"
          >
            <FeatherIcon name="check" class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">{{
              row.is_recurring ? row.frequency || 'Monthly' : 'Paid'
            }}</span>
          </button>
          <button
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-800"
            title="Edit"
            aria-label="Edit"
            @click="emit('edit')"
          >
            <FeatherIcon name="edit-2" class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>

    <ul
      v-if="row._childCount && expanded"
      class="border-t border-gray-50 bg-gray-50/50"
    >
      <li
        v-for="(child, childIdx) in row._children"
        :key="child.name"
        class="flex items-start justify-between gap-2 border-l-2 border-gray-200 py-2.5 pl-8 pr-3 sm:pl-10 sm:pr-4"
        :class="hoverable ? 'hover:bg-gray-50/80' : ''"
      >
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm text-gray-800">
            <span class="mr-1 text-gray-400">↳</span>
            {{ childDisplayTitle(child) }}
            <span
              v-if="row._has_splits && splitPartLabel(childIdx + 1, row._children.length)"
              class="ml-1 rounded bg-gray-100 px-1 py-px text-[10px] font-medium tabular-nums text-gray-600"
              >{{ splitPartLabel(childIdx + 1, row._children.length) }}</span
            >
            <span
              v-if="child.status === 'Paid'"
              class="ml-1 rounded bg-gray-100 px-1 py-px text-[10px] font-medium text-gray-600"
              >Paid</span
            >
          </div>
          <div class="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
            <span
              :class="
                child.status !== 'Paid' && isOverdue(child.due_date, asOf)
                  ? 'font-medium text-red-600'
                  : ''
              "
            >
              {{ dueLabel(child.due_date, asOf) }}
            </span>
            <span
              v-if="isInflowEffect(child.cash_effect)"
              class="rounded px-1 py-px text-[10px] font-medium leading-4 text-green-800 bg-green-50"
            >
              {{ child.cash_effect === 'Setoff' ? 'Setoff' : 'Inflow' }}
            </span>
            <span
              v-else
              class="rounded px-1 py-px text-[10px] font-medium leading-4 text-red-700 bg-red-50"
            >
              Outflow
            </span>
            <span class="tabular-nums text-[11px] text-gray-400">
              · {{ formatINR(child.amount) }}
            </span>
            <span
              v-if="
                child._schedule &&
                isInflowEffect(child.cash_effect) &&
                child.probability != null &&
                Number(child.probability) < 100
              "
              class="tabular-nums text-[11px] text-gray-400"
            >
              · {{ Number(child.probability) }}%
            </span>
          </div>
        </div>
        <div class="flex shrink-0 items-center gap-0.5">
          <button
            v-if="child._schedule && child.status === 'Planned'"
            type="button"
            class="inline-flex h-7 items-center gap-1 rounded px-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            title="Mark this maturity / installment paid"
            @click="emit('mark-paid', child)"
          >
            <FeatherIcon name="check" class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">Paid</span>
          </button>
          <button
            v-if="child._schedule"
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-800"
            title="Edit installment"
            aria-label="Edit installment"
            @click="emit('edit', child)"
          >
            <FeatherIcon name="edit-2" class="h-3.5 w-3.5" />
          </button>
        </div>
      </li>
    </ul>
  </li>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Popover } from 'frappe-ui'
import { isMobileView } from '@/composables/useMobile'
import { formatDate, formatINR } from '@/utils/format'
import {
  commitmentDetailLines,
  displayPlanAmount,
  dueLabel,
  isInflowEffect,
  isOverdue,
  splitPartLabel,
  stripSplitIndexSuffix,
} from '@/utils/commitment'

const props = defineProps({
  row: { type: Object, required: true },
  asOf: { type: String, default: '' },
  expanded: { type: Boolean, default: false },
  marking: { type: Boolean, default: false },
  canMarkPaid: { type: Boolean, default: false },
  canRefresh: { type: Boolean, default: false },
  canFreeze: { type: Boolean, default: false },
  canSplit: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
  freezing: { type: Boolean, default: false },
  /** Slightly denser hover / amount styling used on the Commitments plan list. */
  hoverable: { type: Boolean, default: false },
})

const emit = defineEmits([
  'toggle-group',
  'edit',
  'mark-paid',
  'refresh',
  'freeze',
  'clear-freeze',
  'split',
])

const detailLines = computed(() => commitmentDetailLines(props.row, props.asOf))
const amount = computed(() => displayPlanAmount(props.row))
/** Titles keep the base name; `` · 1/3`` markers are display-only (or stripped). */
const displayTitle = computed(() => stripSplitIndexSuffix(props.row?.title))
/** Split schedule rows = installment count; Account nests = root + children. */
const groupSize = computed(() => {
  const n = Number(props.row?._childCount || 0)
  if (!n) return 0
  return props.row?._has_splits ? n : n + 1
})
const splitLabel = computed(() =>
  props.row?._has_splits || String(props.row?.source_row || '').startsWith('lyqd-split-')
    ? 'Re-split'
    : 'Split',
)

function childDisplayTitle(child) {
  return stripSplitIndexSuffix(child?.title) || displayTitle.value
}
</script>
