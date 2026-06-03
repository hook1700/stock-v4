import { createRouter, createWebHistory } from 'vue-router'
import StockList from '../views/StockList.vue'
import StrategyResults from '../views/StrategyResults.vue'
import DailyRecord from '../views/DailyRecord.vue'

const routes = [
  { path: '/', redirect: '/stocks' },
  { path: '/stocks', name: 'StockList', component: StockList, meta: { title: '股票列表' } },
  { path: '/strategies', name: 'StrategyResults', component: StrategyResults, meta: { title: '策略结果' } },
  { path: '/records', name: 'DailyRecord', component: DailyRecord, meta: { title: '每日记录' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
