<template>
  <Dialog
    :model-value="modelValue"
    :options="{
      title: 'Plan calendar',
      size: '5xl',
    }"
    disable-outside-click-to-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #body-content>
      <p class="mb-2 text-xs text-gray-500">
        Full plan (not just the free-cash horizon). Hover an event for details · ‹ ›
        for months · drag the next due to reschedule.
      </p>
      <div class="mb-3 flex flex-wrap gap-2">
        <FormControl
          v-model="statusFilter"
          class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
          type="select"
          size="sm"
          :options="statusOptions"
        />
        <FormControl
          v-model="effectFilter"
          class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
          type="select"
          size="sm"
          :options="effectOptions"
        />
        <FormControl
          v-model="categoryFilter"
          class="min-w-0 flex-1 sm:max-w-[9.5rem] [&_button]:w-full"
          type="select"
          size="sm"
          :options="categoryOptions"
        />
      </div>
      <div class="h-[min(65vh,34rem)] min-h-[22rem] overflow-hidden">
        <Calendar
          v-if="modelValue"
          :key="`plan-cal-${company.current}`"
          :events="calendarEvents"
          :config="calendarConfig"
          :on-dbl-click="onCalendarEventDblClick"
          :on-cell-click="onCalendarCellClick"
          @update="onCalendarEventUpdate"
          @delete="onCalendarEventDelete"
        >
          <template
            #header="{
              currentMonthYear,
              decrement,
              increment,
              setCalendarDate,
              enabledModes,
              activeView,
              updateActiveView,
            }"
          >
            <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div class="text-base font-medium text-gray-900">
                {{ currentMonthYear }}
              </div>
              <div class="flex shrink-0 flex-wrap items-center gap-1">
                <Button
                  variant="ghost"
                  icon="chevron-left"
                  aria-label="Previous"
                  @click="decrement"
                />
                <Button variant="ghost" label="Today" @click="setCalendarDate()" />
                <Button
                  variant="ghost"
                  icon="chevron-right"
                  aria-label="Next"
                  @click="increment"
                />
                <div
                  v-if="enabledModes?.length > 1"
                  class="ml-1 flex overflow-hidden rounded-md border border-gray-200"
                  role="group"
                  aria-label="Calendar view"
                >
                  <button
                    v-for="mode in enabledModes"
                    :key="mode.value"
                    type="button"
                    class="px-2 py-1 text-xs font-medium"
                    :class="
                      calendarViewIs(activeView, mode.value)
                        ? 'bg-gray-900 text-white'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                    "
                    @click="updateActiveView(mode.value)"
                  >
                    {{ mode.label }}
                  </button>
                </div>
              </div>
            </div>
          </template>
          <template #event-popover-content="{ calendarEvent, close }">
            <div class="w-64 max-w-[85vw] p-3 text-left">
              <div class="mb-2 text-sm font-semibold text-gray-900">
                {{ calendarEvent?.title }}
              </div>
              <dl class="space-y-1.5 text-xs text-gray-600">
                <div
                  v-for="line in detailLines(calendarEvent)"
                  :key="line.label"
                  class="flex justify-between gap-3"
                >
                  <dt class="shrink-0 text-gray-400">{{ line.label }}</dt>
                  <dd class="min-w-0 text-right font-medium text-gray-800">
                    {{ line.value }}
                  </dd>
                </div>
              </dl>
              <div class="mt-3 flex flex-wrap gap-2 border-t border-gray-100 pt-3">
                <Button
                  size="sm"
                  variant="solid"
                  @click="openEdit(calendarEvent); close?.()"
                >
                  Edit
                </Button>
              </div>
              <p class="pt-2 text-[11px] text-gray-400">
                <span v-if="calendarEvent?._isRecurring && !calendarEvent?._isSeriesAnchor">
                  Drag the next due to reschedule · Edit or double-click
                </span>
                <span v-else>Drag to change due date · Edit or double-click</span>
              </p>
            </div>
          </template>
        </Calendar>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Calendar, Dialog, FormControl, call } from 'frappe-ui'
import { toast } from '@/utils/toast'
import { useCompanyStore } from '@/stores/company'
import { useTreasuryCacheStore } from '@/stores/treasuryCache'
import { formatDate, formatINR } from '@/utils/format'
import { commitmentDetailLines, isOverdue as isOverdueDue } from '@/utils/commitment'
import {
  nestPlanRows,
  planSignedNet,
  signedCashAmount,
} from '@/utils/planNest'
import {
  calendarEventDetailLines,
  findPlanRowForEvent,
  parseCalendarEventId,
  planRowsToCalendarEvents,
} from '@/utils/planCalendar'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'edit', 'changed'])

const company = useCompanyStore()
const cache = useTreasuryCacheStore()

const statusFilter = ref('all')
const effectFilter = ref('all')
const categoryFilter = ref('all')

const calendarConfig = {
  defaultMode: 'Month',
  isEditMode: true,
  enableShortcuts: false,
  showIcon: false,
}

const asOfDate = computed(() => new Date().toISOString().slice(0, 10))

const fullPlanRows = computed(() => cache.getPlan(company.current) || [])

function isOverdue(u) {
  return isOverdueDue(u.due_date, asOfDate.value)
}

function isDueSoon(u) {
  const due = u?.due_date
  if (!due) return false
  const a = new Date(asOfDate.value)
  const b = new Date(due)
  const days = Math.round((b - a) / 86400000)
  return days >= 0 && days <= 3
}

function calendarSignedNet(row) {
  if (!row) return 0
  if (row._childCount) return planSignedNet(row)
  if (row.is_recurring) {
    const period =
      row.period_amount != null && row.period_amount !== ''
        ? row.period_amount
        : row.amount
    return signedCashAmount(period, row.cash_effect)
  }
  return planSignedNet(row)
}

const activePlanRows = computed(() =>
  (fullPlanRows.value || []).filter((r) =>
    ['Planned', 'Paid'].includes(r.status || 'Planned'),
  ),
)

const nestedCalendarPlan = computed(() => {
  let nested = nestPlanRows(activePlanRows.value)
  if (statusFilter.value === 'overdue') nested = nested.filter(isOverdue)
  else if (statusFilter.value === 'soon') nested = nested.filter(isDueSoon)
  if (categoryFilter.value !== 'all') {
    nested = nested.filter((r) => r.category === categoryFilter.value)
  }
  if (effectFilter.value === 'outflow') {
    nested = nested.filter((r) => calendarSignedNet(r) > 0.01)
  } else if (effectFilter.value === 'inflow') {
    nested = nested.filter((r) => calendarSignedNet(r) < -0.01)
  }
  return nested
    .slice()
    .sort((a, b) => String(a.due_date || '').localeCompare(String(b.due_date || '')))
})

const calendarEvents = computed(() =>
  planRowsToCalendarEvents(nestedCalendarPlan.value, { asOf: asOfDate.value }),
)

const statusOptions = computed(() => {
  const rows = activePlanRows.value
  return [
    { label: `All (${rows.length})`, value: 'all' },
    { label: `Overdue (${rows.filter(isOverdue).length})`, value: 'overdue' },
    { label: `Due in 3 days (${rows.filter(isDueSoon).length})`, value: 'soon' },
  ]
})

const categoryOptions = computed(() => {
  const set = new Set(activePlanRows.value.map((r) => r.category).filter(Boolean))
  return [
    { label: 'Category', value: 'all' },
    ...[...set].sort().map((c) => ({ label: c, value: c })),
  ]
})

const effectOptions = computed(() => {
  const nested = nestPlanRows(activePlanRows.value)
  const outgoing = nested.filter((r) => calendarSignedNet(r) > 0.01).length
  const incoming = nested.filter((r) => calendarSignedNet(r) < -0.01).length
  return [
    { label: 'Direction', value: 'all' },
    { label: `Outgoing (${outgoing})`, value: 'outflow' },
    { label: `Incoming (${incoming})`, value: 'inflow' },
  ]
})

watch(
  () => [props.modelValue, company.current],
  ([open]) => {
    if (open && company.current) {
      cache.ensurePlan({ company: company.current }).catch(() => {})
    }
  },
  { immediate: true },
)

function calendarViewIs(activeView, mode) {
  const current = activeView?.value ?? activeView
  return current === mode
}

function onCalendarCellClick() {}

function detailLines(calendarEvent) {
  return calendarEventDetailLines(calendarEvent, nestedCalendarPlan.value, asOfDate.value, {
    formatDate,
    formatINR,
    commitmentDetailLines,
  })
}

function openEdit(calendarEvent) {
  const ev = calendarEvent?.value ?? calendarEvent
  const row = findPlanRowForEvent(nestedCalendarPlan.value, ev?.id)
  if (!row) return
  emit('update:modelValue', false)
  emit('edit', row)
}

function onCalendarEventDblClick(payload) {
  openEdit(payload?.calendarEvent ?? payload)
}

function onCalendarEventDelete() {
  toast.info('Use Edit on the payment to cancel it')
  emit('changed')
}

function findPlanRow(name) {
  if (!name) return null
  return (fullPlanRows.value || []).find((p) => p.name === name) || null
}

async function reloadPlan() {
  if (!company.current) return
  await cache.ensurePlan({ company: company.current, force: true })
}

async function onCalendarEventUpdate(event) {
  const newDue = String(event?.fromDate || '').slice(0, 10)
  if (!newDue) return
  const row = findPlanRowForEvent(nestedCalendarPlan.value, event.id)
  if (!row) {
    await reloadPlan()
    emit('changed')
    return
  }
  if (row.parent_payment && !row._schedule) {
    toast.error('Due date follows the parent — drag the parent event instead')
    await reloadPlan()
    return
  }
  const { occurrenceDate } = parseCalendarEventId(event.id)
  const seriesNext = String(row.due_date || '').slice(0, 10)
  if (row.is_recurring && occurrenceDate && occurrenceDate !== seriesNext) {
    toast.info('Drag the next due occurrence to reschedule the series')
    await reloadPlan()
    return
  }
  if (seriesNext === newDue) return

  try {
    if (row._schedule && row.split_name && row.parent_payment) {
      const parent = findPlanRow(row.parent_payment)
      await call('lyqd.api.spa.save_upcoming_payment', {
        doc: {
          name: row.parent_payment,
          company: company.current,
          title: parent?.title || row.title,
          category: parent?.category || row.category || 'Other',
          splits: [
            {
              name: row.split_name,
              due_date: newDue,
              status: row.status || 'Planned',
              probability: row.probability != null ? Number(row.probability) : 100,
            },
          ],
        },
      })
    } else {
      await call('lyqd.api.spa.save_upcoming_payment', {
        doc: {
          name: row.name,
          company: company.current,
          title: row.title,
          category: row.category || 'Other',
          due_date: newDue,
          amount: row.period_amount != null ? row.period_amount : row.amount,
          period_amount: row.period_amount != null ? row.period_amount : row.amount,
          cash_effect: row.cash_effect || 'Outflow',
          is_recurring: row.is_recurring ? 1 : 0,
          frequency: row.frequency,
          recurrence_end: row.recurrence_end,
          status: row.status || 'Planned',
          notes: row.notes,
        },
      })
    }
    toast.success(`Due date → ${formatDate(newDue)}`)
    cache.invalidatePlanOnly(company.current)
    await reloadPlan()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not reschedule')
    await reloadPlan()
    emit('changed')
  }
}
</script>
