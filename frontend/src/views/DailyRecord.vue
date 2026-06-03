<template>
  <div>
    <!-- 页面标题和日期筛选 -->
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: bold;">每日记录</span>
          <div>
            <el-date-picker
              v-model="selectedDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              :shortcuts="dateShortcuts"
              style="margin-right: 10px;"
              @change="handleDateChange"
            />
            <el-button type="primary" @click="loadRecords" :loading="loading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 汇总统计 -->
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="总计交易日" :value="records.length" />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="数据已更新天数"
            :value="records.filter(r => r.data_updated).length"
            value-style="color: #67C23A;"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="策略已执行天数"
            :value="records.filter(r => r.strategy_executed).length"
            value-style="color: #409EFF;"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic title="累计选股信号" :value="totalSignals" />
        </el-col>
      </el-row>
    </el-card>

    <!-- 每日记录列表 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: bold;">历史记录</span>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button label="list">列表视图</el-radio-button>
            <el-radio-button label="calendar">日历视图</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <!-- 列表视图 -->
      <div v-if="viewMode === 'list'">
        <el-table :data="records" v-loading="loading" stripe>
          <el-table-column label="日期" width="120">
            <template #default="scope">
              <div style="font-weight: bold;">{{ scope.row.date }}</div>
              <div style="font-size: 12px; color: #909399;">{{ scope.row.day_of_week }}</div>
            </template>
          </el-table-column>

          <el-table-column label="数据更新" width="100" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.data_updated ? 'success' : 'info'" size="small">
                {{ scope.row.data_updated ? '已更新' : '未更新' }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="策略执行" width="100" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.strategy_executed ? 'success' : 'info'" size="small">
                {{ scope.row.strategy_executed ? `已完成 ${scope.row.completed_strategies}/${scope.row.strategy_count}` : '未执行' }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="选股信号" align="center">
            <template #default="scope">
              <el-tooltip
                :content="`短线: ${scope.row.short_signals} | 中线: ${scope.row.mid_signals} | 长线: ${scope.row.long_signals}`"
                placement="top"
              >
                <div>
                  <el-tag type="danger" size="small" style="margin-right: 4px;">{{ scope.row.short_signals }}</el-tag>
                  <el-tag type="primary" size="small" style="margin-right: 4px;">{{ scope.row.mid_signals }}</el-tag>
                  <el-tag type="warning" size="small">{{ scope.row.long_signals }}</el-tag>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>

          <el-table-column label="涉及股票" width="100" align="center">
            <template #default="scope">
              <span style="font-weight: bold;">{{ scope.row.distinct_stocks }}</span> 只
            </template>
          </el-table-column>

          <el-table-column label="操作" width="120" align="center" fixed="right">
            <template #default="scope">
              <el-button link type="primary" size="small" @click="showDetail(scope.row)">
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 日历视图 -->
      <div v-else>
        <el-calendar v-model="calendarDate">
          <template #date-cell="{ data }">
            <div :class="getCalendarCellClass(data.day)">
              <div class="calendar-date">{{ new Date(data.day).getDate() }}</div>
              <div v-if="getRecordByDate(data.day)" class="calendar-indicator">
                <div v-if="getRecordByDate(data.day).data_updated" class="dot data-dot"></div>
                <div v-if="getRecordByDate(data.day).strategy_executed" class="dot strategy-dot"></div>
                <div v-if="getRecordByDate(data.day).total_signals > 0" class="signal-count">
                  {{ getRecordByDate(data.day).total_signals }}个信号
                </div>
              </div>
            </div>
          </template>
        </el-calendar>
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="`每日详情 - ${selectedRecord?.date}`" width="900px">
      <div v-if="detailLoading" v-loading="detailLoading" style="min-height: 200px;"></div>
      <div v-else-if="detailData">
        <!-- 数据更新状态 -->
        <el-card shadow="never" style="margin-bottom: 15px;">
          <template #header>
            <span style="font-weight: bold;">📊 数据更新</span>
          </template>
          <el-timeline v-if="detailData.data_updates && detailData.data_updates.length > 0">
            <el-timeline-item
              v-for="update in detailData.data_updates"
              :key="update.id"
              :type="update.status === 'completed' ? 'success' : update.status === 'failed' ? 'danger' : 'warning'"
            >
              <div style="display: flex; justify-content: space-between;">
                <span>
                  {{ update.update_type === 'stock_info' ? '股票列表' : '日线数据' }}
                  <el-tag :type="update.status === 'completed' ? 'success' : 'danger'" size="small">
                    {{ update.status === 'completed' ? '成功' : '失败' }}
                  </el-tag>
                </span>
                <span style="color: #909399; font-size: 12px;">
                  {{ update.records_updated }} 条记录
                </span>
              </div>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                {{ update.started_at }} - {{ update.completed_at }}
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="当日无数据更新记录" />
        </el-card>

        <!-- 策略执行状态 -->
        <el-card shadow="never" style="margin-bottom: 15px;">
          <template #header>
            <span style="font-weight: bold;">🎯 策略执行</span>
          </template>
          <el-timeline v-if="detailData.strategy_logs && detailData.strategy_logs.length > 0">
            <el-timeline-item
              v-for="log in detailData.strategy_logs"
              :key="log.id"
              :type="log.status === 'completed' ? 'success' : log.status === 'failed' ? 'danger' : 'warning'"
            >
              <div style="display: flex; justify-content: space-between;">
                <span>
                  策略 #{{ log.strategy_id }}
                  <el-tag :type="log.status === 'completed' ? 'success' : 'danger'" size="small">
                    {{ log.status }}
                  </el-tag>
                </span>
                <span style="color: #909399; font-size: 12px;">
                  <span v-if="log.results_count > 0" style="color: #E6A23C; font-weight: bold;">
                    {{ log.results_count }} 个信号
                  </span>
                </span>
              </div>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                分析 {{ log.stocks_count }} 只股票 | {{ log.completed_at || log.started_at }}
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="当日无策略执行记录" />
        </el-card>

        <!-- 选股信号明细 -->
        <el-card shadow="never" style="margin-bottom: 15px;">
          <template #header>
            <span style="font-weight: bold;">📈 选股信号 ({{ detailData.signals?.length || 0 }})</span>
          </template>
          <el-table v-if="detailData.signals && detailData.signals.length > 0" :data="detailData.signals" max-height="300" size="small">
            <el-table-column prop="stock_code" label="股票代码" width="100" />
            <el-table-column prop="strategy_name" label="策略" width="160" />
            <el-table-column prop="signal_type" label="信号" width="70" align="center">
              <template #default="scope">
                <el-tag type="danger" size="small">{{ scope.row.signal_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="buy_price" label="买入价" width="90" :formatter="priceFormatter" />
            <el-table-column prop="stop_loss" label="止损" width="80" :formatter="priceFormatter" />
            <el-table-column prop="take_profit" label="止盈" width="80" :formatter="priceFormatter" />
            <el-table-column prop="confidence_score" label="置信度" width="80">
              <template #default="scope">
                <span>{{ Math.round((scope.row.confidence_score || 0) * 100) }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="reasoning" label="理由" show-overflow-tooltip min-width="150" />
          </el-table>
          <el-empty v-else description="当日无选股信号" />
        </el-card>

        <!-- 市场概况 -->
        <el-card shadow="never">
          <template #header>
            <span style="font-weight: bold;">📉 市场概况</span>
          </template>
          <el-row :gutter="20">
            <el-col :span="8">
              <div style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #303133;">
                  {{ detailData.market_stats?.total_stocks || 0 }}
                </div>
                <div style="font-size: 12px; color: #909399;">交易股票数</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div style="text-align: center;">
                <div
                  style="font-size: 24px; font-weight: bold;"
                  :style="{ color: (detailData.market_stats?.avg_change || 0) >= 0 ? '#F56C6C' : '#67C23A' }"
                >
                  {{ formatAvgChange(detailData.market_stats?.avg_change) }}
                </div>
                <div style="font-size: 12px; color: #909399;">平均涨跌</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div style="text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #303133;">
                  {{ formatTurnover(detailData.market_stats?.total_turnover) }}
                </div>
                <div style="font-size: 12px; color: #909399;">总成交额</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDailyRecords, getDailyRecordDetail } from '../api/daily_record.js'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const records = ref([])
const viewMode = ref('list')
const calendarDate = ref(new Date())

// 日期范围选择
const today = new Date()
const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
const selectedDateRange = ref([sevenDaysAgo, today])

const dateShortcuts = [
  {
    text: '最近7天',
    value: () => {
      const end = new Date()
      const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000)
      return [start, end]
    }
  },
  {
    text: '最近15天',
    value: () => {
      const end = new Date()
      const start = new Date(end.getTime() - 15 * 24 * 60 * 60 * 1000)
      return [start, end]
    }
  },
  {
    text: '最近30天',
    value: () => {
      const end = new Date()
      const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000)
      return [start, end]
    }
  }
]

const totalSignals = computed(() => {
  return records.value.reduce((sum, r) => sum + (r.total_signals || 0), 0)
})

// 详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedRecord = ref(null)
const detailData = ref(null)

const loadRecords = async () => {
  loading.value = true
  try {
    const params = {}
    if (selectedDateRange.value && selectedDateRange.value.length === 2) {
      const start = selectedDateRange.value[0]
      const end = selectedDateRange.value[1]
      params.days = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1
    }
    const res = await getDailyRecords(params)
    records.value = res.data || []
  } catch (e) {
    ElMessage.error('获取记录失败: ' + e.message)
  }
  loading.value = false
}

const handleDateChange = () => {
  loadRecords()
}

const showDetail = async (row) => {
  selectedRecord.value = row
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await getDailyRecordDetail(row.date)
    detailData.value = res
  } catch (e) {
    ElMessage.error('获取详情失败: ' + e.message)
  }
  detailLoading.value = false
}

// 日历视图辅助函数
const getRecordByDate = (dayStr) => {
  return records.value.find(r => r.date === dayStr)
}

const getCalendarCellClass = (dayStr) => {
  const record = getRecordByDate(dayStr)
  if (!record) return 'calendar-cell'
  if (record.strategy_executed && record.data_updated) return 'calendar-cell highlight'
  return 'calendar-cell'
}

const priceFormatter = (row, col, val) => {
  return val ? parseFloat(val).toFixed(2) : '-'
}

const formatAvgChange = (val) => {
  if (val === null || val === undefined) return '-'
  const num = parseFloat(val)
  return (num >= 0 ? '+' : '') + num.toFixed(2)
}

const formatTurnover = (val) => {
  if (!val) return '-'
  const num = parseFloat(val)
  if (num >= 1e9) {
    return (num / 1e9).toFixed(2) + '亿'
  }
  if (num >= 1e4) {
    return (num / 1e4).toFixed(2) + '万'
  }
  return num.toFixed(0)
}

onMounted(() => {
  loadRecords()
})
</script>

<style scoped>
.calendar-cell {
  min-height: 80px;
  padding: 4px;
  position: relative;
}
.calendar-cell.highlight {
  background-color: #f0f9ff;
}
.calendar-date {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 4px;
}
.calendar-indicator {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.data-dot {
  background-color: #67C23A;
}
.strategy-dot {
  background-color: #409EFF;
}
.signal-count {
  font-size: 10px;
  color: #E6A23C;
}
</style>
