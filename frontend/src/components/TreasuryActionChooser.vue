<template>
  <div>
    <div class="grid items-stretch gap-3 lg:grid-cols-3">
      <!-- Idle CA -->
      <div class="flex h-full min-h-[240px] flex-col rounded-md border border-gray-200 bg-gray-50/80 p-4">
        <div class="text-xs font-medium uppercase tracking-wide text-gray-500">
          Idle current account
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums text-gray-900">
          ~{{ idlePct }}%
          <span class="text-sm font-medium text-gray-500">p.a. typical</span>
        </div>
        <p class="mt-1 text-xs text-gray-500">
          ~{{ formatINR(idleReturn) }} over {{ horizonDays }}d
        </p>
        <ul class="mt-3 flex-1 space-y-1.5 text-sm text-gray-600">
          <li>Usually earns little or no interest</li>
          <li>Often sits idle between payment dates</li>
          <li>Fine when you want maximum flexibility</li>
        </ul>
        <div class="mt-4">
          <Button variant="outline" class="w-full" @click="$emit('leave-in-bank')">
            Leave in bank
          </Button>
        </div>
      </div>

      <!-- Short FD -->
      <div class="flex h-full min-h-[240px] flex-col rounded-md border border-gray-200 bg-white p-4">
        <div class="text-xs font-medium uppercase tracking-wide text-gray-500">
          Short-term bank FD
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums text-gray-900">
          ~{{ fdPct }}%
          <span class="text-sm font-medium text-gray-500">p.a. illustrative</span>
        </div>
        <p class="mt-1 text-xs text-gray-500">
          ~{{ formatINR(fdReturn) }} over {{ horizonDays }}d
        </p>
        <ul class="mt-3 flex-1 space-y-1.5 text-sm text-gray-600">
          <li>Hypothetical rate for examples only</li>
          <li>Bank deposit — different from a mutual fund</li>
          <li>Arranged with your bank — outside LYQD</li>
        </ul>
        <div class="mt-4">
          <Button variant="ghost" class="w-full" disabled>Outside LYQD</Button>
        </div>
      </div>

      <!-- Liquid MF (highlighted) -->
      <div
        class="flex h-full min-h-[240px] flex-col rounded-md border border-gray-900 bg-gray-900 p-4 text-white shadow-sm"
      >
        <div class="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-300">
          Liquid mutual fund
          <a
            v-if="schemeUrl"
            :href="schemeUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex rounded-full p-0.5 text-gray-300 hover:bg-white/10 hover:text-white"
            title="Scheme info"
            aria-label="Scheme info"
            @click.stop
          >
            <FeatherIcon name="info" class="h-3.5 w-3.5" />
          </a>
        </div>
        <div class="mt-2 text-2xl font-semibold tabular-nums">
          ~{{ liquidPct }}%
          <span class="text-sm font-medium text-emerald-400">p.a. illustrative only</span>
        </div>
        <p class="mt-1 text-xs text-gray-400">
          ~{{ formatINR(liquidReturn) }} over {{ horizonDays }}d
        </p>
        <ul class="mt-3 flex-1 space-y-1.5 text-sm text-gray-300">
          <li>Fits short windows between known dues</li>
          <li>Subject to cut-offs, business days and settlement</li>
          <li>Not a bank deposit or fixed-return promise</li>
        </ul>

        <div class="mt-4">
          <Button
            variant="solid"
            class="w-full !bg-white !text-gray-900 hover:!bg-gray-100"
            :loading="creating"
            :disabled="createDisabled"
            @click="$emit('create-instruction')"
          >
            {{ createLabel }}
          </Button>
        </div>
      </div>
    </div>

    <p class="mt-4 text-xs leading-relaxed text-gray-500">{{ MF_DISCLAIMER }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatINR } from '@/utils/format'
import { illustrativeInterest, MF_DISCLAIMER } from '@/utils/scheme'

const props = defineProps({
  amount: { type: Number, default: 0 },
  horizonDays: { type: Number, default: 7 },
  schemeUrl: { type: String, default: null },
  creating: { type: Boolean, default: false },
  createDisabled: { type: Boolean, default: false },
  createLabel: { type: String, default: 'Create liquid fund instruction' },
  idlePct: { type: Number, default: 0 },
  fdPct: { type: Number, default: 3 },
  liquidPct: { type: Number, default: 5.5 },
})

defineEmits(['leave-in-bank', 'create-instruction'])

const idleReturn = computed(() =>
  illustrativeInterest(props.amount, props.idlePct, props.horizonDays),
)
const fdReturn = computed(() =>
  illustrativeInterest(props.amount, props.fdPct, props.horizonDays),
)
const liquidReturn = computed(() =>
  illustrativeInterest(props.amount, props.liquidPct, props.horizonDays),
)
</script>
