import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { createResource, call } from 'frappe-ui'

const STORAGE_KEY = 'lyqd_current_company'

function readStoredCompany() {
  try {
    return localStorage.getItem(STORAGE_KEY) || ''
  } catch (e) {
    return ''
  }
}

function writeStoredCompany(name) {
  try {
    if (name) localStorage.setItem(STORAGE_KEY, name)
    else localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    /* ignore */
  }
}

function pickInitialCompany(companies, serverDefault) {
  const list = companies || []
  const stored = readStoredCompany()
  if (stored && list.includes(stored)) return stored
  if (serverDefault && list.includes(serverDefault)) return serverDefault
  return list[0] || ''
}

export const useCompanyStore = defineStore('company', () => {
  const companies = ref(window.companies || [])
  const current = ref(
    pickInitialCompany(window.companies || [], window.default_company || ''),
  )
  const user = ref(window.user || '')
  const userFullname = ref(window.user_fullname || '')
  const userImage = ref(window.user_image || null)
  const tagline = ref(window.tagline || 'Make idle cash work smarter.')
  const settings = ref({
    in_beta: window.in_beta != null ? Number(window.in_beta) : 1,
  })
  const companySettings = ref(window.company_settings || {})
  const roles = ref(window.roles || [])
  const erpnextIntegrationEnabled = ref(!!window.erpnext_integration_enabled)
  const erpnextInstalled = ref(!!window.erpnext_installed)
  const showAddCompany = ref(false)

  const needsOnboarding = computed(() => !(companies.value || []).length)

  const boot = createResource({
    url: 'lyqd.api.spa.get_boot_data',
    auto: false,
    onSuccess(data) {
      companies.value = data.companies || []
      const next = pickInitialCompany(companies.value, data.default_company || '')
      // Prefer stored / current selection over alphabetical first company
      if (current.value && companies.value.includes(current.value)) {
        // keep current
      } else {
        current.value = next
      }
      if (current.value) writeStoredCompany(current.value)
      user.value = data.user
      userFullname.value = data.user_fullname
      userImage.value = data.user_image || null
      tagline.value = data.tagline || tagline.value
      settings.value = {
        in_beta: 1,
        ...(data.settings || {}),
      }
      if (data.settings?.in_beta == null && data.in_beta != null) {
        settings.value.in_beta = Number(data.in_beta)
      }
      companySettings.value = data.company_settings || {}
      roles.value = data.roles || []
      erpnextIntegrationEnabled.value = !!data.erpnext_integration_enabled
      erpnextInstalled.value = !!data.erpnext_installed
      applyCompanyOverlay(companySettings.value)
      if (needsOnboarding.value) {
        showAddCompany.value = true
      }
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

  function applyCreatedCompany(res) {
    const list = res.companies || []
    if (list.length) {
      companies.value = list
    } else if (res.name && !companies.value.includes(res.name)) {
      companies.value = [...companies.value, res.name]
    }
    const name = res.name || res.company_name
    if (name) {
      current.value = name
      writeStoredCompany(name)
    }
    if (res.books_source || res.enabled != null) {
      applyCompanyOverlay({
        enabled: res.books_source && res.books_source !== 'Manual' ? 1 : 0,
        investment_account_activated: res.investment_account_activated || 0,
        investment_account_requested_on: res.investment_account_requested_on || '',
      })
    }
    showAddCompany.value = false
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
      if (needsOnboarding.value) showAddCompany.value = true
    }
  }

  function setCompany(name) {
    if (name === '__add__') {
      showAddCompany.value = true
      return
    }
    if (!name || name === current.value) return
    current.value = name
    writeStoredCompany(name)
    // Persist as user default so Desk + next full page load keep the same company
    call('lyqd.api.spa.set_current_company', { company: name }).catch(() => {})
  }

  function openAddCompany() {
    showAddCompany.value = true
  }

  watch(
    () => current.value,
    (name, prev) => {
      if (name && name !== prev && name !== '__add__') loadCompanySettings(name)
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

  /** Site-wide badge from LYQD Settings → In Beta (default on). */
  const inBeta = computed(() => {
    const v = settings.value?.in_beta
    if (v == null) return true
    return !!Number(v)
  })

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
    erpnextInstalled,
    investmentAccountActivated,
    inBeta,
    isManager,
    needsOnboarding,
    showAddCompany,
    bootstrap,
    setCompany,
    openAddCompany,
    loadCompanySettings,
    applyCompanyOverlay,
    applyCreatedCompany,
  }
})
