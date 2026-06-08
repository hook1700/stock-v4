import request from './request.js'

export function getStocks(params) {
  return request.get('/stocks/', { params })
}

export function getStockDaily(stockCode, params) {
  return request.get(`/stocks/${stockCode}/daily`, { params })
}

export function fetchStockList(data) {
  return request.post('/stocks/fetch-stock-list', data || {})
}

export function fetchStockDaily(stockCode, data) {
  return request.post(`/stocks/${stockCode}/fetch-daily`, data || {})
}
