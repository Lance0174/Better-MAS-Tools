import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/logs',
      name: 'Logs',
      component: () => import('@/views/logs/index.vue'),
      meta: { title: 'standalone.logs' },
    },
    {
      path: '/mas',
      name: 'Mas',
      component: () => import('@/views/mas/index.vue'),
      meta: { title: 'standalone.mas' },
    },
    {
      path: '/gacha',
      name: 'Gacha',
      component: () => import('@/views/gacha/index.vue'),
      meta: { title: 'standalone.gacha' },
    },
    { path: '/', redirect: '/sign' },
    {
      path: '/sign',
      name: 'CommunitySign',
      component: () => import('@/views/gamesign/index.vue'),
      meta: { title: 'standalone.sign' },
    },
    {
      path: '/activity',
      name: 'CommunityActivity',
      component: () => import('@/views/gamesign/CommunityActivityView.vue'),
      meta: { title: 'standalone.activity' },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/settings/index.vue'),
      meta: { title: 'standalone.settings' },
    },
  ],
})
