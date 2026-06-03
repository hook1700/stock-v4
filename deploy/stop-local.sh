#!/bin/bash
# ============================================
# 本地开发环境停止脚本
# 用法: ./stop-local.sh
# ============================================

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "======================================"
echo "  股票智能分析系统 - 本地停止脚本"
echo "======================================"

# 停止前端
if [ -f "${BASE_DIR}/.frontend.pid" ]; then
    PID=$(cat "${BASE_DIR}/.frontend.pid")
    echo "🎨 停止前端服务 (PID: ${PID})..."
    kill ${PID} 2>/dev/null || true
    rm -f "${BASE_DIR}/.frontend.pid"
fi

# 停止后端
if [ -f "${BASE_DIR}/.backend.pid" ]; then
    PID=$(cat "${BASE_DIR}/.backend.pid")
    echo "🐍 停止后端服务 (PID: ${PID})..."
    kill ${PID} 2>/dev/null || true
    rm -f "${BASE_DIR}/.backend.pid"
fi

# 停止Docker容器
echo "🐳 停止依赖服务 (PostgreSQL + Redis)..."
cd "${BASE_DIR}"
docker-compose down 2>/dev/null || true

echo ""
echo "✅ 所有服务已停止"
