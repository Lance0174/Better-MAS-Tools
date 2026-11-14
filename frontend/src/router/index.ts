import { createRouter, createWebHashHistory } from 'vue-router'
import { isAndroidLocal } from '@/services/android'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/logs',
      name: 'Logs',
      component: () => import('@/views/logs/index.vue'),
      meta: { title: 'standalone.logs' },
    },
    ...(import.meta.env.BMAT_ANDROID || isAndroidLocal
      ? []
      : [
          {
            path: '/mas',
            name: 'Mas',
            component: () => import('@/views/mas/index.vue'),
            meta: { title: 'standalone.mas' },
          },
        ]),
    {
      path: '/wiki',
      name: 'Wiki',
      component: () => import('@/views/wiki/index.vue'),
      meta: { title: 'standalone.wiki' },
    },
    {
      path: '/calendar',
      name: 'Calendar',
      component: () => import('@/views/calendar/index.vue'),
      meta: {
        title: 'standalone.calendar',
        primary: true,
        subtitle: 'standalone.ui.calendarSubtitle',
      },
    },
    {
      path: '/gacha',
      name: 'Gacha',
      component: () => import('@/views/gacha/index.vue'),
      meta: { title: 'standalone.gacha', primary: true, subtitle: 'standalone.ui.gachaSubtitle' },
    },
    { path: '/', redirect: '/home' },
    {
      path: '/home',
      name: 'Home',
      component: () => import('@/views/home/index.vue'),
      meta: { title: 'standalone.home', primary: true },
    },
    {
      path: '/sign',
      name: 'CommunitySign',
      component: () => import('@/views/gamesign/index.vue'),
      meta: { title: 'standalone.homeSignResults', parent: '/more' },
    },
    {
      path: '/accounts',
      name: 'Accounts',
      component: () => import('@/views/gamesign/index.vue'),
      meta: { title: 'standalone.accountList', parent: '/more' },
    },
    {
      path: '/more',
      name: 'More',
      component: () => import('@/views/more/index.vue'),
      meta: { title: 'standalone.more', primary: true, subtitle: 'standalone.ui.moreSubtitle' },
    },
    {
      path: '/activity',
      name: 'CommunityActivity',
      component: () => import('@/views/home/ActivityOverview.vue'),
      meta: { title: 'standalone.activity', primary: true, subtitle: 'standalone.noteAccountHint' },
    },
    ...(import.meta.env.BMAT_ANDROID || isAndroidLocal
      ? []
      : [
          {
            path: '/remote',
            name: 'RemoteControl',
            component: () => import('@/views/remote/index.vue'),
            meta: { title: 'standalone.remote' },
          },
        ]),
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/settings/index.vue'),
      meta: { title: 'standalone.settings' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/home' },
  ],
})
