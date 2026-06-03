import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useStrategyStore = defineStore('strategy', () => {
  // 策略列表
  const strategies = ref([])
  const strategyResults = ref([])
  const resultTotal = ref(0)
  const resultPage = ref(1)
  const resultPageSize = ref(20)
  const resultsLoading = ref(false)
  const executing = ref(false)

  // 筛选
  const filterType = ref('')
  const filterStrategyId = ref(null)
  const selectedDate = ref(new Date())

  const shortStrategies = computed(() => strategies.value.filter(s => s.type === 'short'))
  const midStrategies = computed(() => strategies.value.filter(s => s.type === 'mid'))
  const longStrategies = computed(() => strategies.value.filter(s => s.type === 'long'))

  const strategyStats = computed(() => {
    return {
      short: shortStrategies.value.length,
      mid: midStrategies.value.length,
      long: longStrategies.value.length
    }
  })

  const setStrategies = (data) => {
    strategies.value = data
  }

  const setResults = (data, total) => {
    strategyResults.value = data
    resultTotal.value = total
  }

  const setPage = (page, size) => {
    resultPage.value = page
    resultPageSize.value = size
  }

  const setFilters = (type, strategyId) => {
    filterType.value = type
    filterStrategyId.value = strategyId
  }

  const setDate = (date) => {
    selectedDate.value = date
  }

  const setExecuting = (val) => {
    executing.value = val
  }

  return {
    strategies,
    strategyResults,
    resultTotal,
    resultPage,
    resultPageSize,
    resultsLoading,
    executing,
    filterType,
    filterStrategyId,
    selectedDate,
    shortStrategies,
    midStrategies,
    longStrategies,
    strategyStats,
    setStrategies,
    setResults,
    setPage,
    setFilters,
    setDate,
    setExecuting
  }
})
