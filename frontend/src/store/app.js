import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 侧边栏折叠状态
  const sidebarCollapsed = ref(false)

  // 页面加载状态
  const globalLoading = ref(false)
  const loadingText = ref('')

  // 系统信息
  const systemStatus = ref(null)
  const lastUpdated = ref(null)

  // 通知消息
  const notifications = ref([])

  const sidebarWidth = computed(() => sidebarCollapsed.value ? '64px' : '200px')

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const setGlobalLoading = (loading, text = '') => {
    globalLoading.value = loading
    loadingText.value = text
  }

  const setSystemStatus = (status) => {
    systemStatus.value = status
    if (status?.last_data_update) {
      lastUpdated.value = status.last_data_update
    }
  }

  const addNotification = (notification) => {
    const id = Date.now()
    notifications.value.push({
      id,
      ...notification,
      timestamp: new Date().toISOString()
    })
    // 自动移除
    setTimeout(() => {
      removeNotification(id)
    }, 5000)
  }

  const removeNotification = (id) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  return {
    sidebarCollapsed,
    globalLoading,
    loadingText,
    systemStatus,
    lastUpdated,
    notifications,
    sidebarWidth,
    toggleSidebar,
    setGlobalLoading,
    setSystemStatus,
    addNotification,
    removeNotification
  }
})
