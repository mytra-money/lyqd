<template>
  <div
    class="flex flex-col items-center justify-center px-6 py-14 text-center sm:py-16"
    role="status"
  >
    <div class="mb-5" aria-hidden="true">
      <!-- Banks -->
      <svg
        v-if="variant === 'bank'"
        class="mx-auto h-28 w-28"
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect x="22" y="38" width="76" height="48" rx="8" fill="#F9FAFB" stroke="#E5E7EB" stroke-width="2" />
        <path d="M30 54h60" stroke="#E5E7EB" stroke-width="2" />
        <rect x="30" y="62" width="22" height="14" rx="3" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2" />
        <path d="M60 68h24M60 74h16" stroke="#E5E7EB" stroke-width="2.5" stroke-linecap="round" />
        <circle cx="84" cy="86" r="18" fill="#ECFDF5" stroke="#61D3A0" stroke-width="2" />
        <path d="M84 80v12M78 86h12" stroke="#171717" stroke-width="2.5" stroke-linecap="round" />
      </svg>
      <!-- From books -->
      <svg
        v-else-if="variant === 'books'"
        class="mx-auto h-28 w-28"
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect x="24" y="28" width="44" height="64" rx="5" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="2" />
        <rect x="40" y="22" width="48" height="70" rx="5" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2" />
        <path d="M52 42h24M52 52h18M52 62h22" stroke="#E5E7EB" stroke-width="3" stroke-linecap="round" />
        <circle cx="82" cy="84" r="16" fill="#ECFDF5" stroke="#61D3A0" stroke-width="2" />
        <path
          d="M82 76.5c-0.6 3-3.6 6.6-5.4 8.4-2 2-3.6 4.4-3.6 7 0 5 4 9 9 9s9-4 9-9c0-2.6-1.6-5-3.6-7-1.8-1.8-4.8-5.4-5.4-8.4z"
          fill="#171717"
        />
      </svg>
      <!-- Filter / no match -->
      <svg
        v-else-if="variant === 'filter'"
        class="mx-auto h-28 w-28"
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle cx="56" cy="54" r="26" fill="#F9FAFB" stroke="#E5E7EB" stroke-width="2" />
        <circle cx="56" cy="54" r="12" stroke="#D1D5DB" stroke-width="2.5" />
        <path d="M65 63l16 16" stroke="#D1D5DB" stroke-width="3" stroke-linecap="round" />
        <path d="M34 92h52" stroke="#E5E7EB" stroke-width="3" stroke-linecap="round" />
      </svg>
      <!-- Invest / free cash -->
      <svg
        v-else-if="variant === 'invest'"
        class="mx-auto h-28 w-28"
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle cx="60" cy="58" r="30" fill="#F9FAFB" stroke="#E5E7EB" stroke-width="2" />
        <path
          d="M48 70c4-14 10-24 12-28 2 4 8 14 12 28"
          stroke="#D1D5DB"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path d="M52 58h16" stroke="#D1D5DB" stroke-width="2.5" stroke-linecap="round" />
        <circle cx="82" cy="86" r="18" fill="#ECFDF5" stroke="#61D3A0" stroke-width="2" />
        <path d="M82 80v12M76 86h12" stroke="#171717" stroke-width="2.5" stroke-linecap="round" />
      </svg>
      <!-- Portfolio / holdings -->
      <svg
        v-else-if="variant === 'portfolio'"
        class="mx-auto h-28 w-28"
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect x="28" y="40" width="64" height="44" rx="8" fill="#F9FAFB" stroke="#E5E7EB" stroke-width="2" />
        <path d="M44 40v-4a8 8 0 0 1 8-8h16a8 8 0 0 1 8 8v4" stroke="#D1D5DB" stroke-width="2" />
        <path d="M42 58h12M42 66h20M42 74h16" stroke="#E5E7EB" stroke-width="2.5" stroke-linecap="round" />
        <circle cx="82" cy="86" r="18" fill="#ECFDF5" stroke="#61D3A0" stroke-width="2" />
        <path d="M82 80v12M76 86h12" stroke="#171717" stroke-width="2.5" stroke-linecap="round" />
      </svg>
      <!-- Plan / commitments (default) -->
      <svg
        v-else
        class="mx-auto h-28 w-28"
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect x="26" y="24" width="68" height="76" rx="8" fill="#F9FAFB" stroke="#E5E7EB" stroke-width="2" />
        <rect x="38" y="16" width="44" height="16" rx="4" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2" />
        <path d="M42 52h36M42 64h28M42 76h32" stroke="#E5E7EB" stroke-width="3" stroke-linecap="round" />
        <circle cx="78" cy="86" r="18" fill="#ECFDF5" stroke="#61D3A0" stroke-width="2" />
        <path d="M78 80v12M72 86h12" stroke="#171717" stroke-width="2.5" stroke-linecap="round" />
      </svg>
    </div>
    <h3 class="text-sm font-semibold text-gray-900">{{ title }}</h3>
    <p v-if="description" class="mt-1.5 max-w-[16rem] text-sm leading-relaxed text-gray-500">
      {{ description }}
    </p>
    <div v-if="$slots.actions" class="mt-5 flex flex-wrap items-center justify-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  /** plan | books | filter | bank | invest | portfolio */
  variant: { type: String, default: 'plan' },
})
</script>
