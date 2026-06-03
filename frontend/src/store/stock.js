import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useStockStore = defineStore('stock', () => {
  // 股票列表
  const stockList = ref([])
  const stockTotal = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const searchQuery = ref('')
  const loading = ref(false)

  // 当前选中股票
  const selectedStock = ref(null)
  const selectedStockDaily = ref([])

  // 筛选条件
  const filterMarket = ref('')
  const filterIndustry = ref('')

  const industries = computed(() => {
    const set = new Set(stockList.value.map(s => s.industry).filter(Boolean))
    return Array.from(set).sort()
  })

  const setStockList = (stocks, total) => {
    stockList.value = stocks
    stockTotal.value = total
  }

  const setPage = (page, size) => {
    currentPage.value = page
    pageSize.value = size
  }

  const selectStock = (stock) => {
    selectedStock.value = stock
  }

  const setStockDaily = (data) => {
    selectedStockDaily.value = data
  }

  const setFilters = (market, industry) => {
    filterMarket.value = market
    filterIndustry.value = industry
  }

  return {
    stockList,
    stockTotal,
    currentPage,
    pageSize,
    searchQuery,
    loading,
    selectedStock,
    selectedStockDaily,
    filterMarket,
    filterIndustry,
    industries,
    setStockList,
    setPage,
    selectStock,
    setStockDaily,
    setFilters
  }
})
