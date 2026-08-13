import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'project',
        name: 'Project',
        component: () => import('@/views/Project.vue'),
        meta: { title: '知识图谱管理' }
      },
      {
        path: 'model',
        name: 'Model',
        component: () => import('@/views/Model.vue'),
        meta: { title: '图谱模型管理' }
      },
      {
        path: 'extraction',
        name: 'Extraction',
        component: () => import('@/views/Extraction.vue'),
        meta: { title: 'LLM 知识抽取' }
      },
      {
        path: 'extraction/kos',
        name: 'KosExtraction',
        component: () => import('@/views/KosExtraction.vue'),
        meta: { title: 'KOS 知识抽取' }
      },
      {
        path: 'extraction/structure',
        name: 'StructureExtraction',
        component: () => import('@/views/StructureExtraction.vue'),
        meta: { title: '结构化数据抽取' }
      },
      {
        path: 'extraction/dl',
        name: 'DlExtraction',
        component: () => import('@/views/DlExtraction.vue'),
        meta: { title: '深度学习抽取' }
      },
      {
        path: 'corpus',
        name: 'Corpus',
        component: () => import('@/views/Corpus.vue'),
        meta: { title: '语料管理' }
      },
      {
        path: 'explore',
        name: 'Explore',
        component: () => import('@/views/Explore.vue'),
        meta: { title: '图谱探索' }
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/Chat.vue'),
        meta: { title: '智能问答' }
      },
      {
        path: 'platform/user',
        name: 'UserManage',
        component: () => import('@/views/platform/UserManage.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'platform/role',
        name: 'RoleManage',
        component: () => import('@/views/platform/RoleManage.vue'),
        meta: { title: '角色管理' }
      },
      {
        path: 'platform/profile',
        name: 'Profile',
        component: () => import('@/views/platform/Profile.vue'),
        meta: { title: '个人信息' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/home'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, _from, next) => {
  document.title = (to.meta.title as string) || 'KGraph'
  if (to.path === '/login') {
    next()
    return
  }
  const userStore = useUserStore()
  if (!userStore.userInfo) {
    // 尝试获取当前登录用户
    const ok = await userStore.fetchCurrentUser()
    if (!ok) {
      next('/login')
      return
    }
  }
  next()
})

export default router
