import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { userApi } from '@/api'

export interface UserInfo {
  id: number
  userAccount: string
  userName?: string
  userAvatar?: string
  userProfile?: string
  userRole?: string
}

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null)
  const loading = ref(false)

  /** 是否为管理员 */
  const isAdmin = computed(() => userInfo.value?.userRole === 'admin')

  async function fetchCurrentUser(): Promise<boolean> {
    try {
      const res = await userApi.getLoginUser()
      if (res.code === 0 && res.data) {
        userInfo.value = res.data as UserInfo
        return true
      }
      return false
    } catch {
      return false
    }
  }

  async function login(userAccount: string, userPassword: string): Promise<boolean> {
    loading.value = true
    try {
      const res = await userApi.login(userAccount, userPassword)
      if (res.code === 0) {
        await fetchCurrentUser()
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await userApi.logout()
    } finally {
      userInfo.value = null
    }
  }

  return {
    userInfo,
    loading,
    isAdmin,
    fetchCurrentUser,
    login,
    logout
  }
})
