<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: bold;">股票池</span>
          <div style="display: flex; gap: 10px;">
            <el-button type="success" @click="handleFetchStockList" :loading="fetchLoading">
              <el-icon><Download /></el-icon>
              拉取股票数据
            </el-button>
            <el-input
              v-model="searchQuery"
              placeholder="搜索股票代码或名称"
              style="width: 280px;"
              clearable
              @keyup.enter="handleSearch"
            >
              <template #append>
                <el-button @click="handleSearch">
                  <el-icon><Search /></el-icon>
                </el-button>
              </template>
            </el-input>
          </div>
        </div>
      </template>
      
      <el-table :data="stocks" v-loading="loading" stripe>
        <el-table-column prop="stock_code" label="股票代码" width="120" />
        <el-table-column prop="stock_name" label="股票名称" width="150" />
        <el-table-column prop="market" label="市场" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.market === 'SH' ? 'danger' : 'success'">
              {{ scope.row.market }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" width="180" />
        <el-table-column prop="listing_date" label="上市日期" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewDetail(scope.row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        style="margin-top: 20px;"
      />
    </el-card>
    
    <!-- 股票详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="selectedStock?.stock_name + ' (' + selectedStock?.stock_code + ')'" width="800px">
      <div style="margin-bottom: 10px; display: flex; justify-content: flex-end;">
        <el-button type="primary" @click="handleFetchDaily" :loading="fetchDailyLoading" size="small">
          <el-icon><Download /></el-icon>
          拉取最新日线数据
        </el-button>
      </div>
      <el-table :data="dailyData" v-loading="detailLoading" max-height="400">
        <el-table-column prop="trade_date" label="日期" width="120" />
        <el-table-column prop="close_price" label="收盘价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="open_price" label="开盘价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="high_price" label="最高价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="low_price" label="最低价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="volume" label="成交量" width="120" />
        <el-table-column prop="turnover" label="成交额" width="120" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download } from '@element-plus/icons-vue'
import { getStocks, getStockDaily, fetchStockList, fetchStockDaily } from '../api/stock.js'

const stocks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const searchQuery = ref('')

const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedStock = ref(null)
const dailyData = ref([])

const fetchLoading = ref(false)
const fetchDailyLoading = ref(false)

const loadStocks = async () => {
  loading.value = true
  try {
    const res = await getStocks({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchQuery.value || undefined
    })
    stocks.value = res.data || []
    total.value = res.total || 0
  } catch (e) {
    console.error('获取股票列表失败:', e)
  }
  loading.value = false
}

const handleSearch = () => {
  currentPage.value = 1
  loadStocks()
}

const handleSizeChange = (val) => {
  pageSize.value = val
  loadStocks()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  loadStocks()
}

const viewDetail = async (stock) => {
  selectedStock.value = stock
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await getStockDaily(stock.stock_code)
    dailyData.value = res.data || []
  } catch (e) {
    console.error('获取日线数据失败:', e)
  }
  detailLoading.value = false
}

const handleFetchStockList = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要从数据源拉取最新股票列表数据吗？这将会更新数据库中的股票信息。',
      '确认拉取',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      }
    )
    
    fetchLoading.value = true
    const res = await fetchStockList({ use_history_api: true })
    
    if (res.success) {
      ElMessage.success(`拉取成功！共更新 ${res.count || 0} 只股票`)
      // 刷新列表
      loadStocks()
    } else {
      ElMessage.error(`拉取失败: ${res.error || '未知错误'}`)
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('拉取股票列表失败:', e)
      ElMessage.error(`拉取失败: ${e.message || e}`)
    }
  } finally {
    fetchLoading.value = false
  }
}

const handleFetchDaily = async () => {
  if (!selectedStock.value) return
  
  try {
    await ElMessageBox.confirm(
      `确定要拉取 ${selectedStock.value.stock_name} (${selectedStock.value.stock_code}) 的最新日线数据吗？`,
      '确认拉取',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      }
    )
    
    fetchDailyLoading.value = true
    const res = await fetchStockDaily(selectedStock.value.stock_code, { days: 365 })
    
    if (res.success) {
      ElMessage.success(`拉取成功！共更新 ${res.count || 0} 条日线数据`)
      // 刷新日线数据
      const dailyRes = await getStockDaily(selectedStock.value.stock_code)
      dailyData.value = dailyRes.data || []
    } else {
      ElMessage.error(`拉取失败: ${res.error || '未知错误'}`)
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('拉取日线数据失败:', e)
      ElMessage.error(`拉取失败: ${e.message || e}`)
    }
  } finally {
    fetchDailyLoading.value = false
  }
}

const priceFormatter = (row, col, val) => {
  return val ? parseFloat(val).toFixed(2) : '-'
}

onMounted(() => {
  loadStocks()
})
</script>