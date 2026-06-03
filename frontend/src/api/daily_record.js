import request from './request.js'

export function getDailyRecords(params) {
  return request.get('/daily-records/', { params })
}

export function getDailyRecordDetail(recordDate) {
  return request.get(`/daily-records/${recordDate}`)
}
