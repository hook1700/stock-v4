import request from './request.js'

export function getStocks(params) {
  return request.get('/stocks/', { params })
}

export function getStockDaily(stockCode, params) {
  return request.get(`/stocks/${stockCode}/daily`, { params })
}
