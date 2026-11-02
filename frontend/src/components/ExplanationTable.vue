<template>
  <div class="overflow-hidden rounded-xl border border-black/5">
    <table class="min-w-full text-sm">
      <thead class="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
        <tr>
          <th class="px-4 py-3 w-12"></th>
          <th class="px-4 py-3">Item</th>
          <th class="px-4 py-3 text-right">Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(line, idx) in lines"
          :key="idx"
          class="border-t border-black/5"
          :class="line.kind === 'total' ? 'bg-gray-50 font-semibold' : 'bg-white'"
        >
          <td class="px-4 py-3 tabular-nums text-gray-500">{{ line.sign }}</td>
          <td class="px-4 py-3">
            <div>{{ line.label }}</div>
            <div class="mt-0.5 flex flex-wrap gap-2 text-xs text-gray-500">
              <span v-if="line.category" class="rounded bg-gray-100 px-1.5 py-0.5">{{
                line.category
              }}</span>
              <span v-if="line.due_date">Due {{ formatDate(line.due_date) }}</span>
              <span v-if="line.ref_name" class="font-mono">{{ line.ref_name }}</span>
            </div>
          </td>
          <td class="px-4 py-3 text-right tabular-nums">{{ formatINR(line.amount) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { formatDate, formatINR } from '@/utils/format'

defineProps({
  lines: { type: Array, default: () => [] },
})
</script>
