import { defineStore } from 'pinia'
import { api, setCsrfToken } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    loaded: false,
  }),
  getters: {
    isLogin: (state) => !!state.user,
    role: (state) => state.user?.role || '',
    menus: (state) => state.user?.menus || [],
  },
  actions: {
    async login(username, password) {
      const data = await api.login({ username, password })
      setCsrfToken(data.csrf_token)
      this.user = data.user
      this.loaded = true
      return data.user
    },
    async fetchMe() {
      try {
        this.user = await api.me()
        setCsrfToken()
      } catch {
        this.user = null
      } finally {
        this.loaded = true
      }
      return this.user
    },
    async logout() {
      try {
        await api.logout()
      } finally {
        this.user = null
        setCsrfToken('')
      }
    },
  },
})
