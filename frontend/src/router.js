import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('@/pages/Dashboard.vue') },
  { path: '/surplus', name: 'Surplus', component: () => import('@/pages/Surplus.vue') },
  { path: '/upcoming', name: 'Upcoming', component: () => import('@/pages/Upcoming.vue') },
  { path: '/invest', name: 'Invest', component: () => import('@/pages/Invest.vue') },
  { path: '/proposals', redirect: '/invest' },
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
  { path: '/schemes', name: 'Schemes', component: () => import('@/pages/Schemes.vue') },
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
