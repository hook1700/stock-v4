<template>
  <div>
    <!-- 策略概览卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="8">
        <el-card>
          <div style="font-size: 14px; color: #909399; margin-bottom: 8px;">短线策略</div>
          <div style="font-size: 32px; font-weight: bold; color: #67C23A;">
            {{ strategyStats.short || 0 }}
          </div>
          <div style="font-size: 12px; color: #909399;">今日选股</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <div style="font-size: 14px; color: #909399; margin-bottom: 8px;">中线策略</div>
          <div style="font-size: 32px; font-weight: bold; color: #409EFF;">
            {{ strategyStats.mid || 0 }}
          </div>
          <div style="font-size: 12px; color: #909399;">今日选股</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <div style="font-size: 14px; color: #909399; margin-bottom: 8px;">长线策略</div>
          <div style="font-size: 32px; font-weight: bold; color: #E6A23C;">
            {{ strategyStats.long || 0 }}
          </div>
          <div style="font-size: 12px; color: #909399;">今日选股</div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 策略执行控制 -->
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: bold;">策略执行</span>
          <div>
            <el-date-picker
              v-model="selectedDate"
              type="date"
              placeholder="选择分析日期"
              style="margin-right: 10px;"
            />
            <el-button type="primary" @click="executeAll" :loading="executing">
              全部执行
            </el-button>
          </div>
        </div>
      </template>
      
      <el-row :gutter="10">
        <el-col :span="8">
          <div style="font-weight: bold; margin-bottom: 10px;">短线策略</div>
          <div v-for="s in shortStrategies" :key="s.id" style="margin-bottom: 6px;">
            <el-tag effect="plain" style="margin-right: 5px;">{{ s.name }}</el-tag>
            <el-button link type="primary" size="small" @click="runSingle(s.id)">
              执行
            </el-button>
          </div>
        </el-col>
        <el-col :span="8">
          <div style="font-weight: bold; margin-bottom: 10px;">中线策略</div>
          <div v-for="s in midStrategies" :key="s.id" style="margin-bottom: 6px;">
            <el-tag effect="plain" style="margin-right: 5px;">{{ s.name }}</el-tag>
            <el-button link type="primary" size="small" @click="runSingle(s.id)">
              执行
            </el-button>
          </div>
        </el-col>
        <el-col :span="8">
          <div style="font-weight: bold; margin-bottom: 10px;">长线策略</div>
          <div v-for="s in longStrategies" :key="s.id" style="margin-bottom: 6px;">
            <el-tag effect="plain" style="margin-right: 5px;">{{ s.name }}</el-tag>
            <el-button link type="primary" size="small" @click="runSingle(s.id)">
              执行
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <!-- 筛选结果列表 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: bold;">筛选结果</span>
          <div>
            <el-select v-model="filterType" placeholder="策略类型" style="width: 120px; margin-right: 10px;">
              <el-option label="全部" value="" />
              <el-option label="短线" value="short" />
              <el-option label="中线" value="mid" />
              <el-option label="长线" value="long" />
            </el-select>
            <el-select v-model="filterStrategy" placeholder="选择策略" clearable style="width: 180px; margin-right: 10px;">
              <el-option
                v-for="s in allStrategies"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
            <el-button @click="loadResults">刷新</el-button>
          </div>
        </div>
      </template>
      
      <el-table :data="results" v-loading="loading" stripe>
        <el-table-column prop="stock_code" label="股票代码" width="110" />
        <el-table-column prop="stock_name" label="股票名称" width="120" />
        <el-table-column prop="strategy_name" label="策略名称" width="180" />
        <el-table-column prop="signal_type" label="信号" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.signal_type === 'buy' ? 'danger' : 'info'">{{ scope.row.signal_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="buy_price" label="买入价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="stop_loss" label="止损价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="take_profit" label="止盈价" width="100" :formatter="priceFormatter" />
        <el-table-column prop="confidence_score" label="置信度" width="80">
          <template #default="scope">
            <el-progress
              :percentage="Math.round((scope.row.confidence_score || 0) * 100)"
              :color="confidenceColor"
              :show-text="true"
              style="width: 60px;"
            />
          </template>
        </el-table-column>
        <el-table-column prop="reasoning" label="选股理由" min-width="300" show-overflow-tooltip />
        <el-table-column prop="trade_date" label="日期" width="110" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button link type="primary" size="small" @click="showDetail(scope.row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="loadResults"
        style="margin-top: 20px;"
      />
    </el-card>
    
    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="'选股详情'" width="600px">
      <div v-if="selectedResult">
        <p><strong>股票代码:</strong> {{ selectedResult.stock_code }}</p>
        <p><strong>股票名称:</strong> {{ selectedResult.stock_name }}</p>
        <p><strong>策略:</strong> {{ selectedResult.strategy_name }}</p>
        <p><strong>信号类型:</strong> {{ selectedResult.signal_type }}</p>
        <p><strong>建议买入价:</strong> {{ formatPrice(selectedResult.buy_price) }} 元</p>
        <p><strong>止损价:</strong> {{ formatPrice(selectedResult.stop_loss) }} 元</p>
        <p><strong>止盈价:</strong> {{ formatPrice(selectedResult.take_profit) }} 元</p>
        <p><strong>置信度:</strong> {{ Math.round((selectedResult.confidence_score || 0) * 100) }}%</p>
        <p><strong>选股理由:</strong></p>
        <el-alert type="info" :closable="false" style="margin-top: 8px;">
          {{ selectedResult.reasoning }}
        </el-alert>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getStrategies, executeStrategies, getStrategyResults } from '../api/strategy.js'
import { ElMessage } from 'element-plus'

const strategies = ref([])
const results = ref([])
const total = ref(0)
const loading = ref(false)
const executing = ref(false)

const currentPage = ref(1)
const pageSize = ref(20)
const selectedDate = ref(new Date())
const filterType = ref('')
const filterStrategy = ref(null)

const detailVisible = ref(false)
const selectedResult = ref(null)

const allStrategies = computed(() => strategies.value)
const shortStrategies = computed(() => strategies.value.filter(s => s.type === 'short'))
const midStrategies = computed(() => strategies.value.filter(s => s.type === 'mid'))
const longStrategies = computed(() => strategies.value.filter(s => s.type === 'long'))

const strategyStats = ref({})

const confidenceColor = (percentage) => {
  if (percentage < 50) return '#909399'
  if (percentage < 70) return '#E6A23C'
  return '#67C23A'
}

const loadStrategies = async () => {
  try {
    const res = await getStrategies()
    strategies.value = res.data || []
  } catch (e) {
    console.error('获取策略失败:', e)
  }
}

const loadResults = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      trade_date: selectedDate.value ? formatDate(selectedDate.value) : undefined
    }
    if (filterStrategy.value) {
      params.strategy_id = filterStrategy.value
    }
    
    const res = await getStrategyResults(params)
    results.value = res.data || []
    total.value = res.total || 0
    
    // 统计
    const stats = { short: 0, mid: 0, long: 0 }
    results.value.forEach(r => {
      const s = strategies.value.find(x => x.id === r.strategy_id)
      if (s) {
        stats[s.type] = (stats[s.type] || 0) + 1
      }
    })
    strategyStats.value = stats
  } catch (e) {
    console.error('获取结果失败:', e)
  }
  loading.value = false
}

const executeAll = async () => {
  executing.value = true
  try {
    const date = selectedDate.value ? formatDate(selectedDate.value) : undefined
    await executeStrategies({ trade_date: date })
    ElMessage.success('策略执行完成')
    loadResults()
  } catch (e) {
    ElMessage.error('执行失败: ' + e.message)
  }
  executing.value = false
}

const runSingle = async (id) => {
  executing.value = true
  try {
    const date = selectedDate.value ? formatDate(selectedDate.value) : undefined
    await executeStrategies({ strategy_ids: [id], trade_date: date })
    ElMessage.success('策略执行完成')
    loadResults()
  } catch (e) {
    ElMessage.error('执行失败: ' + e.message)
  }
  executing.value = false
}

const showDetail = (row) => {
  selectedResult.value = row
  detailVisible.value = true
}

const priceFormatter = (row, col, val) => {
  return val ? parseFloat(val).toFixed(2) : '-'
}

const formatPrice = (val) => {
  return val ? parseFloat(val).toFixed(2) : '-'
}

const formatDate = (date) => {
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadStrategies()
  loadResults()
})
</script>