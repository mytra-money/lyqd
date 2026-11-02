import './index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  FrappeUI,
  Button,
  FormControl,
  Dialog,
  Badge,
  FeatherIcon,
  Avatar,
  Dropdown,
  setConfig,
  frappeRequest,
} from 'frappe-ui'

import App from './App.vue'
import router from './router'

let app = createApp(App)
let pinia = createPinia()

setConfig('resourceFetcher', frappeRequest)

app.use(FrappeUI)
app.use(pinia)
app.use(router)

for (const [name, component] of Object.entries({
  Button,
  FormControl,
  Dialog,
  Badge,
  FeatherIcon,
  Avatar,
  Dropdown,
})) {
  app.component(name, component)
}

function mount() {
  app.mount('#app')
}

if (import.meta.env.DEV) {
  frappeRequest({
    url: '/api/method/lyqd.www.lyqd.get_context_for_dev',
  })
    .then((values) => {
      for (let key in values) {
        window[key] = values[key]
      }
      if (!window.csrf_token && values.csrf_token) {
        window.csrf_token = values.csrf_token
      }
      mount()
    })
    .catch(() => mount())
} else {
  mount()
}
