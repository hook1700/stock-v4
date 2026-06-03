import request from './request.js'

export function getSystemStatus() {
  return request.get('/system/status')
}

export function triggerDataUpdate() {
  return request.post('/system/update-data')
}

export function startScheduler() {
  return request.post('/system/scheduler/start')
}

export function stopScheduler() {
  return request.post('/system/scheduler/stop')
}
