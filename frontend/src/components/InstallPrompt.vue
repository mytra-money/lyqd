<template>
  <Dialog v-model="showDialog" :options="{ title: 'Install LYQD' }">
    <template #body-content>
      <p class="text-sm text-gray-600">
        Add LYQD to your home screen for quick access to cash position, commitments, and free
        cash.
      </p>
    </template>
    <template #actions>
      <Button variant="solid" class="w-full" @click="install">Install</Button>
      <Button variant="ghost" class="w-full" @click="showDialog = false">Not now</Button>
    </template>
  </Dialog>

  <div
    v-if="iosInstallMessage"
    class="fixed inset-x-3 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-40 rounded-lg border border-gray-200 bg-white p-3 shadow-lg md:bottom-4 md:max-w-sm"
  >
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0 text-sm text-gray-800">
        <div class="font-medium text-gray-900">Install LYQD</div>
        <p class="mt-1 text-xs text-gray-600">
          Tap
          <FeatherIcon name="share" class="mx-0.5 inline h-3.5 w-3.5 text-blue-600" />
          then <span class="font-medium">Add to Home Screen</span>.
        </p>
      </div>
      <button
        type="button"
        class="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        aria-label="Close"
        @click="dismissIos"
      >
        <FeatherIcon name="x" class="h-4 w-4" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const deferredPrompt = ref(null)
const showDialog = ref(false)
const iosInstallMessage = ref(false)

function isIos() {
  const ua = window.navigator.userAgent.toLowerCase()
  return /iphone|ipad|ipod/.test(ua)
}

function isStandalone() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  )
}

function dismissIos() {
  iosInstallMessage.value = false
  localStorage.setItem('lyqdIosInstallPromptShown', 'true')
}

function onBeforeInstall(e) {
  e.preventDefault()
  deferredPrompt.value = e
  if (isIos() && !isStandalone()) {
    iosInstallMessage.value = true
  } else if (localStorage.getItem('lyqdInstallPromptDismissed') !== 'true') {
    showDialog.value = true
  }
}

function onInstalled() {
  showDialog.value = false
  deferredPrompt.value = null
}

function install() {
  if (!deferredPrompt.value) return
  deferredPrompt.value.prompt()
  showDialog.value = false
  localStorage.setItem('lyqdInstallPromptDismissed', 'true')
}

onMounted(() => {
  if (
    isIos() &&
    !isStandalone() &&
    localStorage.getItem('lyqdIosInstallPromptShown') !== 'true'
  ) {
    iosInstallMessage.value = true
  }
  window.addEventListener('beforeinstallprompt', onBeforeInstall)
  window.addEventListener('appinstalled', onInstalled)
})

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', onBeforeInstall)
  window.removeEventListener('appinstalled', onInstalled)
})
</script>
