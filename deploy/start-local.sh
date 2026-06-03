#!/bin/bash
# ============================================
# 本地开发环境启动脚本
# 用法: ./start-local.sh [backend|frontend|all]
# ============================================

set -e

MODE=${1:-all}
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "======================================"
echo "  股票智能分析系统 - 本地启动脚本"
echo "  模式: ${MODE}"
echo "======================================"

case $MODE in
    backend)
        echo ""
        echo "🐍 启动后端服务..."
        cd "${BASE_DIR}/backend"

        # 检查 Python 环境
        if ! command -v python3 &> /dev/null; then
            echo "❌ 未找到 python3，请先安装 Python 3.11+"
            exit 1
        fi

        # 检查虚拟环境
        if [ ! -d "venv" ]; then
            echo "  创建虚拟环境..."
            python3 -m venv venv
        fi

        # 激活虚拟环境
        source venv/bin/activate || source venv/Scripts/activate

        # 安装依赖
        echo "  安装依赖..."
        pip install -q -r requirements.txt

        # 启动服务
        echo "  启动 FastAPI 服务..."
        echo "  API文档: http://localhost:8000/docs"
        uvicorn app:app --host 0.0.0.0 --port 8000 --reload
        ;;

    frontend)
        echo ""
        echo "🎨 启动前端服务..."
        cd "${BASE_DIR}/frontend"

        # 检查 Node.js
        if ! command -v node &> /dev/null; then
            echo "❌ 未找到 node，请先安装 Node.js 20+"
            exit 1
        fi

        # 安装依赖
        echo "  安装依赖..."
        npm install

        # 启动开发服务器
        echo "  启动 Vite 开发服务器..."
        echo "  前端地址: http://localhost:3000"
        npm run dev
        ;;

    all|*)
        echo ""
        echo "🐍 启动依赖服务 (PostgreSQL + Redis)..."
        cd "${BASE_DIR}"

        # 检查 .env
        if [ ! -f .env ]; then
            echo "  创建 .env 文件..."
            cp .env.example .env
        fi

        # 启动基础设施
        docker compose up -d db redis

        echo ""
        echo "⏳ 等待数据库就绪..."
        sleep 5

        echo ""
        echo "🐍 启动后端服务..."
        cd "${BASE_DIR}/backend"

        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        source venv/bin/activate || source venv/Scripts/activate
        pip install -q -r requirements.txt

        # 后台启动后端
        nohup uvicorn app:app --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
        echo $! > ../.backend.pid
        echo "  后端已启动 (PID: $(cat ../.backend.pid))"
        echo "  API文档: http://localhost:8000/docs"

        echo ""
        echo "🎨 启动前端服务..."
        cd "${BASE_DIR}/frontend"
        npm install
        nohup npm run dev > ../logs/frontend.log 2>&1 &
        echo $! > ../.frontend.pid
        echo "  前端已启动 (PID: $(cat ../.frontend.pid))"
        echo "  前端地址: http://localhost:3000"

        echo ""
        echo "======================================"
        echo "  所有服务已启动"
        echo "======================================"
        echo ""
        echo "访问地址:"
        echo "  前端界面: http://localhost:3000"
        echo "  API文档:  http://localhost:8000/docs"
        echo ""
        echo "日志文件:"
        echo "  后端: $(realpath ../logs/backend.log)"
        echo "  前端: $(realpath ../logs/frontend.log)"
        echo ""
        echo "停止服务: ./deploy/stop-local.sh"
        ;;
esac
