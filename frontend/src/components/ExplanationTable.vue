<template>
  <div class="overflow-hidden rounded-xl border border-black/5">
    <table class="min-w-full text-sm">
      <thead class="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
        <tr>
          <th class="w-10 px-2 py-3"></th>
          <th class="px-4 py-3 w-12"></th>
          <th class="px-4 py-3">Item</th>
          <th class="px-4 py-3 text-right">Amount</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(line, idx) in lines" :key="rowKey(line, idx)">
          <tr
            class="border-t border-black/5"
            :class="line.kind === 'total' ? 'bg-gray-50 font-semibold' : 'bg-white'"
          >
            <td class="px-2 py-3">
              <button
                v-if="lineChildCount(line)"
                type="button"
                class="flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                :aria-expanded="isExpanded(line, idx)"
                :aria-label="isExpanded(line, idx) ? 'Collapse group' : 'Expand group'"
                @click="toggle(line, idx)"
              >
                <FeatherIcon
                  :name="isExpanded(line, idx) ? 'chevron-down' : 'chevron-right'"
                  class="h-3.5 w-3.5"
                />
              </button>
            </td>
            <td class="px-4 py-3 tabular-nums text-gray-500">{{ line.sign }}</td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap items-center gap-2">
                <span>{{ line.label }}</span>
                <span
                  v-if="lineChildCount(line)"
                  class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600"
                >
                  Group · {{ lineChildCount(line) + 1 }}
                </span>
              </div>
              <div class="mt-0.5 flex flex-wrap gap-2 text-xs text-gray-500">
                <span v-if="line.category" class="rounded bg-gray-100 px-1.5 py-0.5">{{
                  line.category
                }}</span>
                <span v-if="line.due_date">Due {{ formatDate(line.due_date) }}</span>
                <span
                  v-if="lineChildCount(line) && line.gl_amount != null"
                  class="tabular-nums text-[11px] text-gray-400"
                >
                  · GL {{ line.gl_sign === '+' ? '−' : '' }}{{ formatINR(line.gl_amount) }}
                </span>
                <span v-if="line.ref_name" class="font-mono">{{ line.ref_name }}</span>
              </div>
            </td>
            <td class="px-4 py-3 text-right">
              <div
                class="tabular-nums"
                :class="lineChildCount(line) ? 'text-base font-semibold text-gray-900' : ''"
              >
                {{ formatINR(line.amount) }}
              </div>
              <div
                v-if="lineChildCount(line)"
                class="text-[10px] font-medium uppercase tracking-wide text-gray-400"
              >
                Net
              </div>
            </td>
          </tr>
          <tr
            v-for="(child, cidx) in isExpanded(line, idx) ? lineChildren(line) : []"
            :key="rowKey(child, `${idx}-${cidx}`)"
            class="border-t border-black/5 bg-gray-50/50"
          >
            <td class="px-2 py-2"></td>
            <td class="px-4 py-2 tabular-nums text-gray-400">{{ child.sign }}</td>
            <td class="border-l-2 border-gray-200 py-2 pl-4">
              <div class="text-gray-800">
                <span class="mr-1 text-gray-400">↳</span>
                {{ child.label }}
              </div>
              <div class="mt-0.5 flex flex-wrap gap-2 text-xs text-gray-500">
                <span v-if="child.category" class="rounded bg-gray-100 px-1.5 py-0.5">{{
                  child.category
                }}</span>
                <span v-if="child.due_date">Due {{ formatDate(child.due_date) }}</span>
                <span class="tabular-nums text-[11px] text-gray-400">
                  · GL {{ child.sign === '+' ? '−' : '' }}{{ formatINR(child.amount) }}
                </span>
                <span v-if="child.ref_name" class="font-mono">{{ child.ref_name }}</span>
              </div>
            </td>
            <td class="px-4 py-2 text-right text-xs text-gray-400">—</td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { formatDate, formatINR } from '@/utils/format'

defineProps({
  lines: { type: Array, default: () => [] },
})

/** Expanded group keys; default collapsed. */
const expanded = ref({})

function lineChildren(line) {
  return Array.isArray(line?.children) ? line.children : []
}

function lineChildCount(line) {
  if (line?.child_count) return Number(line.child_count)
  return lineChildren(line).length
}

function rowKey(line, fallback) {
  return line?.ref_name || `line-${fallback}`
}

function expandKey(line, idx) {
  return String(line?.ref_name || idx)
}

function isExpanded(line, idx) {
  return !!expanded.value[expandKey(line, idx)]
}

function toggle(line, idx) {
  const key = expandKey(line, idx)
  expanded.value = { ...expanded.value, [key]: !expanded.value[key] }
}
</script>
