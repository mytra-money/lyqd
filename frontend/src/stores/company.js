import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { createResource, call } from 'frappe-ui'

export const useCompanyStore = defineStore('company', () => {
  const companies = ref(window.companies || [])
  const current = ref(window.default_company || companies.value[0] || '')
  const user = ref(window.user || '')
  const userFullname = ref(window.user_fullname || '')
  const userImage = ref(window.user_image || null)
  const tagline = ref(window.tagline || 'Make idle cash work smarter.')
  const settings = ref({})
  const companySettings = ref(window.company_settings || {})
  const roles = ref(window.roles || [])
  const erpnextIntegrationEnabled = ref(!!window.erpnext_integration_enabled)

  const boot = createResource({
    url: 'lyqd.api.spa.get_boot_data',
    auto: false,
    onSuccess(data) {
      companies.value = data.companies || []
      if (!current.value || !companies.value.includes(current.value)) {
        current.value = data.default_company || companies.value[0] || ''
      }
      user.value = data.user
      userFullname.value = data.user_fullname
      userImage.value = data.user_image || null
      tagline.value = data.tagline || tagline.value
      settings.value = data.settings || {}
      companySettings.value = data.company_settings || {}
      roles.value = data.roles || []
      erpnextIntegrationEnabled.value = !!data.erpnext_integration_enabled
      applyCompanyOverlay(companySettings.value)
    },
  })

  function applyCompanyOverlay(cs) {
    if (!cs) return
    settings.value = {
      ...(settings.value || {}),
      investment_account_activated: cs.investment_account_activated || 0,
      investment_account_requested_on: cs.investment_account_requested_on || '',
    }
    erpnextIntegrationEnabled.value = !!cs.enabled
  }

  async function loadCompanySettings(name) {
    if (!name) {
      companySettings.value = {}
      applyCompanyOverlay({})
      return
    }
    try {
      const cs = await call('lyqd.api.spa.get_erpnext_settings', { company: name })
      companySettings.value = cs || {}
      applyCompanyOverlay(companySettings.value)
    } catch (e) {
      companySettings.value = {}
    }
  }

  async function bootstrap() {
    try {
      await boot.fetch()
    } catch (e) {
      // boot from window is enough for first paint
    }
  }

  function setCompany(name) {
    current.value = name
  }

  watch(
    () => current.value,
    (name, prev) => {
      if (name && name !== prev) loadCompanySettings(name)
    },
  )

  const isManager = computed(
    () =>
      roles.value.includes('System Manager') ||
      roles.value.includes('LYQD Manager') ||
      user.value === 'Administrator',
  )

  const investmentAccountActivated = computed(
    () => !!Number(settings.value?.investment_account_activated || 0),
  )

  return {
    companies,
    current,
    user,
    userFullname,
    userImage,
    tagline,
    settings,
    companySettings,
    roles,
    erpnextIntegrationEnabled,
    investmentAccountActivated,
    isManager,
    bootstrap,
    setCompany,
    loadCompanySettings,
    applyCompanyOverlay,
  }
})
