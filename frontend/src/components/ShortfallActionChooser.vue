<template>
  <div>
    <div class="grid items-stretch gap-3 lg:grid-cols-3">
      <!-- Draw on facility -->
      <div class="flex h-full min-h-[240px] flex-col rounded-md border border-gray-200 bg-gray-50/80 p-4">
        <div class="text-xs font-medium uppercase tracking-wide text-gray-500">
          Draw on CC / OD
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums text-gray-900">
          ~{{ ccPct }}%
          <span class="text-sm font-medium text-gray-500">p.a. typical</span>
        </div>
        <p class="mt-1 text-xs text-gray-500">
          <template v-if="unusedHeadroom > 0.01">
            Unused headroom {{ formatINR(unusedHeadroom) }}
          </template>
          <template v-else>No unused facility headroom</template>
        </p>
        <ul class="mt-3 flex-1 space-y-1.5 text-sm text-gray-600">
          <li>Use sanctioned limit you already have</li>
          <li>Drawn balances already reduce free cash</li>
          <li>Arranged with your bank — outside LYQD</li>
        </ul>
        <div class="mt-4">
          <Button
            variant="outline"
            class="w-full"
            :disabled="unusedHeadroom < 0.01"
            @click="$emit('use-facility')"
          >
            {{ unusedHeadroom > 0.01 ? 'Use facility' : 'No headroom' }}
          </Button>
        </div>
      </div>

      <!-- Redeem liquid -->
      <div class="flex h-full min-h-[240px] flex-col rounded-md border border-gray-200 bg-white p-4">
        <div class="text-xs font-medium uppercase tracking-wide text-gray-500">
          Redeem liquid holdings
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums text-gray-900">
          {{ formatINR(liquidTotal) }}
          <span class="text-sm font-medium text-gray-500">available</span>
        </div>
        <p class="mt-1 text-xs text-gray-500">
          <template v-if="canRedeem">
            Suggest redeem {{ formatINR(redemptionNeed) }}
          </template>
          <template v-else>No holdings to redeem this horizon</template>
        </p>
        <ul class="mt-3 flex-1 space-y-1.5 text-sm text-gray-600">
          <li>Unwinds parked surplus to cover dues</li>
          <li>Subject to cut-offs and settlement</li>
          <li>Creates a redeem instruction in LYQD</li>
        </ul>
        <div class="mt-4">
          <Button
            variant="outline"
            class="w-full"
            :loading="creating && createSide === 'Redeem'"
            :disabled="!canRedeem || createDisabled"
            @click="$emit('create-redeem')"
          >
            {{
              canRedeem
                ? createDisabled
                  ? createDisabledLabel
                  : 'Create redeem instruction'
                : 'Nothing to redeem'
            }}
          </Button>
        </div>
      </div>

      <!-- Funding fit (highlighted) -->
      <div
        class="flex h-full min-h-[240px] flex-col rounded-md border border-gray-900 bg-gray-900 p-4 text-white shadow-sm"
      >
        <div class="text-xs font-medium uppercase tracking-wide text-gray-300">
          Funding fit
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums">
          WCDL / trade
          <span class="text-sm font-medium text-emerald-400">structure</span>
        </div>
        <p class="mt-1 text-xs text-gray-400">
          {{ fundingFitHint }}
        </p>
        <ul class="mt-3 flex-1 space-y-1.5 text-sm text-gray-300">
          <li>When CC is blunt or expensive for the cycle</li>
          <li>Working-capital / trade lines may fit better</li>
          <li>Mytra reviews need from this forecast</li>
        </ul>
        <div class="mt-4">
          <Button
            variant="solid"
            class="w-full !bg-white !text-gray-900 hover:!bg-gray-100"
            @click="$emit('funding-fit')"
          >
            Review with Mytra
          </Button>
        </div>
      </div>
    </div>

    <p class="mt-4 text-xs leading-relaxed text-gray-500">
      Facility draw and structured finance are outside LYQD instructions. Redeem creates a LYQD
      instruction when holdings can cover part of the gap. Rates are illustrative only.
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatINR } from '@/utils/format'

const props = defineProps({
  shortfallAmount: { type: Number, default: 0 },
  unusedHeadroom: { type: Number, default: 0 },
  availableWithCc: { type: Number, default: 0 },
  availableWithCcIsShortfall: { type: Boolean, default: false },
  liquidTotal: { type: Number, default: 0 },
  redemptionNeed: { type: Number, default: 0 },
  creating: { type: Boolean, default: false },
  createDisabled: { type: Boolean, default: false },
  createDisabledLabel: { type: String, default: 'Instruction already open' },
  createSide: { type: String, default: '' },
  ccPct: { type: Number, default: 10.5 },
})

defineEmits(['use-facility', 'create-redeem', 'funding-fit'])

const canRedeem = computed(
  () => Number(props.liquidTotal) > 0.01 && Number(props.redemptionNeed) > 0.01,
)

const fundingFitHint = computed(() => {
  if (props.availableWithCcIsShortfall) {
    return `Still short after facility · need ${formatINR(props.shortfallAmount)}`
  }
  if (Number(props.availableWithCc) > 0.01) {
    return `Facility covers gap · Available (CC) ${formatINR(props.availableWithCc)}`
  }
  return `Shortfall ${formatINR(props.shortfallAmount)} this horizon`
})
</script>
