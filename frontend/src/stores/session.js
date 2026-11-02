import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

function getCookie(name) {
  return document.cookie
    .split('; ')
    .map((c) => c.split('='))
    .find(([k]) => k === name)?.[1]
}

export const useSessionStore = defineStore('session', () => {
  const user = getCookie('user_id') ? decodeURIComponent(getCookie('user_id')) : null

  const logout = createResource({
    url: 'logout',
    onSuccess() {
      window.location.href = `/login?redirect-to=${encodeURIComponent('/lyqd')}`
    },
  })

  return { user, logout }
})
