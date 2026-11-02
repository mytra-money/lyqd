import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { createResource } from 'frappe-ui'

export const useCompanyStore = defineStore('company', () => {
  const companies = ref(window.companies || [])
  const current = ref(window.default_company || companies.value[0] || '')
  const user = ref(window.user || '')
  const userFullname = ref(window.user_fullname || '')
  const userImage = ref(window.user_image || null)
  const tagline = ref(window.tagline || 'Make idle cash work smarter.')
  const settings = ref({})
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
      roles.value = data.roles || []
      erpnextIntegrationEnabled.value = !!data.erpnext_integration_enabled
    },
  })

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
    roles,
    erpnextIntegrationEnabled,
    investmentAccountActivated,
    isManager,
    bootstrap,
    setCompany,
  }
})
