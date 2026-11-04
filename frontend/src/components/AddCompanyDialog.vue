<template>
  <Dialog
    :model-value="modelValue"
    :options="{
      title: required ? 'Create your LYQD Company' : 'Add LYQD Company',
      size: 'xl',
    }"
    :disable-outside-click-to-close="required"
    @update:model-value="onOpenChange"
  >
    <template #body-header>
      <div class="mb-6 flex items-center justify-between">
        <h3 class="text-2xl font-semibold leading-6 text-gray-900">
          {{ required ? 'Create your LYQD Company' : 'Add LYQD Company' }}
        </h3>
        <Button v-if="!required" variant="ghost" @click="close">
          <template #icon>
            <FeatherIcon name="x" class="h-4 w-4" />
          </template>
        </Button>
      </div>
    </template>

    <template #body-content>
      <div class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-2">
          <FormControl
            v-model="form.company_name"
            label="Company name"
            class="sm:col-span-2"
            required
          />
          <FormControl v-model="form.abbr" label="Abbr (optional)" />
        </div>

        <div class="space-y-3 rounded-md border border-gray-200 p-3">
          <label class="flex items-center gap-3">
            <input v-model="form.enabled" type="checkbox" class="rounded border-gray-300" />
            <span class="text-sm font-medium text-gray-900">Enable ERPNext</span>
          </label>

          <label
            v-if="form.enabled && erpnextInstalled"
            class="flex items-center gap-3 border-t border-gray-100 pt-3"
          >
            <input
              v-model="form.is_erpnext_in_the_current_site"
              type="checkbox"
              class="rounded border-gray-300"
            />
            <span class="text-sm font-medium text-gray-900">ERPNext is on this site</span>
          </label>

          <div
            v-if="form.enabled && showRemoteFields"
            class="space-y-3 border-t border-gray-100 pt-3"
          >
            <FormControl
              v-model="form.remote_site_url"
              label="ERPNext site URL"
              placeholder="https://erp.example.com"
            />
            <div class="grid gap-3 sm:grid-cols-2">
              <FormControl v-model="form.remote_api_key" label="API Key" />
              <FormControl
                v-model="form.remote_api_secret"
                type="password"
                label="API Secret"
              />
            </div>
            <FormControl
              v-if="remoteCompanies.length"
              v-model="form.books_company"
              type="select"
              label="Remote company"
              :options="remoteCompanies"
              required
            />
            <FormControl
              v-else
              v-model="form.books_company"
              label="Remote company"
              placeholder="Exact ERPNext Company name"
              required
            />
            <p class="text-xs text-gray-500">
              Required for multi-company sites — LYQD binds recommendations to this books company.
            </p>
            <div class="flex flex-wrap gap-2">
              <Button
                variant="outline"
                :loading="probing"
                :disabled="!canProbe"
                @click="probeRemote"
              >
                Connect
              </Button>
              <span v-if="probeOk" class="self-center text-xs text-emerald-700">Connected</span>
            </div>
          </div>

          <div
            v-else-if="form.enabled && form.is_erpnext_in_the_current_site"
            class="space-y-1 border-t border-gray-100 pt-3"
          >
            <FormControl
              v-if="localCompanies.length"
              v-model="form.books_company"
              type="select"
              label="Books company"
              :options="localCompanies"
              required
            />
            <FormControl
              v-else
              v-model="form.books_company"
              label="Books company"
              placeholder="Exact ERPNext Company name on this site"
              required
            />
            <p class="text-xs text-gray-500">
              Required — binds this LYQD Company to one ERPNext Company on this site.
            </p>
          </div>
        </div>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>
    </template>

    <template #actions>
      <Button variant="solid" :loading="saving" :disabled="!canSave" @click="save">
        {{ required ? 'Create company' : 'Add company' }}
      </Button>
      <Button v-if="!required" variant="outline" @click="close">Cancel</Button>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { call, toast } from 'frappe-ui'
import { useCompanyStore } from '@/stores/company'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'created'])

const company = useCompanyStore()
const erpnextInstalled = computed(() => !!company.erpnextInstalled)

const form = reactive({
  company_name: '',
  abbr: '',
  enabled: false,
  is_erpnext_in_the_current_site: false,
  books_company: '',
  remote_site_url: '',
  remote_api_key: '',
  remote_api_secret: '',
})

const saving = ref(false)
const probing = ref(false)
const probeOk = ref(false)
const remoteCompanies = ref([])
const localCompanies = ref([])
const error = ref('')

const showRemoteFields = computed(
  () => form.enabled && !(erpnextInstalled.value && form.is_erpnext_in_the_current_site),
)

const booksSource = computed(() => {
  if (!form.enabled) return 'Manual'
  if (erpnextInstalled.value && form.is_erpnext_in_the_current_site) return 'This Site'
  return 'Other Site'
})

const canProbe = computed(
  () =>
    !!(form.remote_site_url || '').trim() &&
    !!(form.remote_api_key || '').trim() &&
    !!(form.remote_api_secret || '').trim(),
)

const canSave = computed(() => {
  if (!(form.company_name || '').trim()) return false
  if (booksSource.value === 'Manual') return true
  // This Site / Other Site — books company is mandatory (multi-company safe)
  if (!(form.books_company || '').trim()) return false
  if (booksSource.value === 'Other Site') return canProbe.value
  return true
})

async function loadLocalCompanies() {
  if (!erpnextInstalled.value) {
    localCompanies.value = []
    return
  }
  try {
    const res = await call('lyqd.api.spa.list_local_erpnext_companies')
    localCompanies.value = res.companies || []
  } catch {
    localCompanies.value = []
  }
}

function reset() {
  form.company_name = ''
  form.abbr = ''
  form.enabled = false
  form.is_erpnext_in_the_current_site = false
  form.books_company = ''
  form.remote_site_url = ''
  form.remote_api_key = ''
  form.remote_api_secret = ''
  remoteCompanies.value = []
  probeOk.value = false
  error.value = ''
}

function close() {
  if (props.required) return
  emit('update:modelValue', false)
}

function onOpenChange(open) {
  if (!open && props.required) {
    emit('update:modelValue', true)
    return
  }
  emit('update:modelValue', open)
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      error.value = ''
      probeOk.value = false
      // Default this-site when ERPNext is available
      if (erpnextInstalled.value && form.enabled) {
        form.is_erpnext_in_the_current_site = true
      }
      loadLocalCompanies()
    } else if (!props.required) {
      reset()
    }
  },
)

watch(
  () => form.enabled,
  (on) => {
    if (!on) {
      form.is_erpnext_in_the_current_site = false
      probeOk.value = false
      remoteCompanies.value = []
      return
    }
    // CRM: if ERPNext is on this site, default the checkbox on
    form.is_erpnext_in_the_current_site = !!erpnextInstalled.value
  },
)

watch(
  () => form.is_erpnext_in_the_current_site,
  () => {
    probeOk.value = false
    remoteCompanies.value = []
  },
)

async function probeRemote() {
  probing.value = true
  error.value = ''
  probeOk.value = false
  try {
    const res = await call('lyqd.api.spa.probe_remote_erpnext_connection', {
      url: form.remote_site_url,
      api_key: form.remote_api_key,
      api_secret: form.remote_api_secret,
      company: form.books_company || null,
      skip_mirror: 1,
    })
    remoteCompanies.value = res.companies || []
    if (res.company) {
      form.books_company = res.company
    } else if ((res.companies || []).length > 1 && !(form.books_company || '').trim()) {
      toast.success('Select the remote company for this LYQD Company')
    }
    probeOk.value = true
    toast.success(res.message || 'Connected')
  } catch (e) {
    error.value = e.messages?.[0] || e.message || 'Connection failed'
    toast.error(error.value)
  } finally {
    probing.value = false
  }
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = ''
  try {
    const source = booksSource.value
    if (source !== 'Manual' && !(form.books_company || '').trim()) {
      error.value = 'Books company is required'
      toast.error(error.value)
      return
    }
    const payload = {
      company_name: form.company_name.trim(),
      abbr: (form.abbr || '').trim() || null,
      books_source: source,
      books_company: source === 'Manual' ? null : form.books_company.trim(),
      mirror_banks: source === 'Other Site' ? 1 : 0,
    }
    if (source === 'Other Site') {
      payload.remote_site_url = form.remote_site_url.trim()
      payload.remote_api_key = form.remote_api_key.trim()
      payload.remote_api_secret = form.remote_api_secret
    }
    const res = await call('lyqd.api.spa.create_lyqd_company', payload)
    company.applyCreatedCompany(res)
    toast.success(`Company ${res.name || payload.company_name} ready`)
    if (res.bank_mirror_error) toast.error(res.bank_mirror_error)
    emit('created', res)
    emit('update:modelValue', false)
    reset()
  } catch (e) {
    error.value = e.messages?.[0] || e.message || 'Could not create company'
    toast.error(error.value)
  } finally {
    saving.value = false
  }
}
</script>
