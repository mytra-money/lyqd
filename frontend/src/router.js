import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/surplus', name: 'Surplus', component: () => import('@/pages/Surplus.vue') },
  { path: '/upcoming', name: 'Upcoming', component: () => import('@/pages/Upcoming.vue') },
  { path: '/proposal', name: 'Proposal', component: () => import('@/pages/Proposal.vue') },
  // Back-compat
  { path: '/invest', redirect: '/proposal' },
  { path: '/proposals', redirect: '/proposal' },
  {
    path: '/policy',
    redirect: { path: '/settings', query: { tab: 'liquidity' } },
  },
  { path: '/cash', name: 'Cash', component: () => import('@/pages/Cash.vue') },
  { path: '/runs', redirect: '/surplus' },
  {
    path: '/runs/:name',
    name: 'RunDetail',
    component: () => import('@/pages/RunDetail.vue'),
    props: true,
  },
  // Schemes are Mytra-managed; SPA no longer exposes a catalogue editor.
  { path: '/schemes', redirect: '/proposal' },
  {
    path: '/instructions',
    name: 'Instructions',
    component: () => import('@/pages/Instructions.vue'),
  },
  { path: '/holdings', name: 'Holdings', component: () => import('@/pages/Holdings.vue') },
  { path: '/settings', name: 'Settings', component: () => import('@/pages/Settings.vue') },
]

const router = createRouter({
  history: createWebHistory('/lyqd'),
  routes,
})

export default router
