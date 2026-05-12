import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, logout as apiLogout, verifyToken } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<any>(null)
  const token = ref<string | null>(null)

  const isAuthenticated = computed(() => !!user.value && !!token.value)
  const isAdmin = computed(() => user.value?.is_admin === true)
  const username = computed(() => user.value?.username || '')

  async function login(email: string, password: string) {
    const result = await apiLogin(email, password)
    token.value = result.access_token
    user.value = result.user
    localStorage.setItem('token', result.access_token)
    localStorage.setItem('user', JSON.stringify(result.user))
    return result
  }

  async function register(email: string, usernameVal: string, password: string, confirmPassword: string) {
    const result = await apiRegister(email, usernameVal, password, confirmPassword)
    token.value = result.access_token
    user.value = result.user
    localStorage.setItem('token', result.access_token)
    localStorage.setItem('user', JSON.stringify(result.user))
    return result
  }

  async function logout() {
    try {
      await apiLogout()
    } catch {
      // 即使后端登出失败，也要清理本地状态
    }
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function checkAuth(): Promise<boolean> {
    if (!token.value) {
      clearAuth()
      return false
    }
    try {
      const result = await verifyToken()
      if (result.valid && result.user) {
        user.value = result.user
        localStorage.setItem('user', JSON.stringify(result.user))
        return true
      } else {
        clearAuth()
        return false
      }
    } catch {
      clearAuth()
      return false
    }
  }

  function initFromStorage() {
    const storedToken = localStorage.getItem('token')
    const storedUser = localStorage.getItem('user')
    if (storedToken && storedUser) {
      token.value = storedToken
      try {
        user.value = JSON.parse(storedUser)
      } catch {
        clearAuth()
      }
    }
    // 异步验证 token 有效性
    if (token.value) {
      checkAuth()
    }
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    user,
    token,
    isAuthenticated,
    isAdmin,
    username,
    login,
    register,
    logout,
    checkAuth,
    initFromStorage,
    clearAuth
  }
})
