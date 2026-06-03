import request from './request.js'

export function getStrategies() {
  return request.get('/strategies/')
}

export function executeStrategies(data) {
  return request.post('/strategies/execute', data)
}

export function getStrategyResults(params) {
  return request.get('/strategies/results', { params })
}

export function rerunStrategy(strategyId, data) {
  return request.post(`/strategies/${strategyId}/rerun`, data)
}
