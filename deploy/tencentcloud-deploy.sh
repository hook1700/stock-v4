#!/bin/bash
# ============================================
# 腾讯云服务器部署脚本
# 用法: ./tencentcloud-deploy.sh [prod|dev]
# ============================================

set -e

# 配置
ENV=${1:-prod}
SERVER_HOST="${TENCENT_CLOUD_IP}"
SSH_KEY="${TENCENT_CLOUD_KEY:-~/.ssh/tencent_cloud}"
REMOTE_DIR="/opt/stock-analysis"
PROJECT_NAME="stock-analysis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "======================================"
echo "  股票智能分析系统 - 腾讯云部署脚本"
echo "  环境: ${ENV}"
echo "  时间: ${TIMESTAMP}"
echo "======================================"

# 检查必要的环境变量
if [ -z "$TENCENT_CLOUD_IP" ]; then
    echo "❌ 错误: TENCENT_CLOUD_IP 环境变量未设置"
    echo "  请执行: export TENCENT_CLOUD_IP=你的服务器IP"
    exit 1
fi

# 步骤1: 本地构建镜像并推送到腾讯云镜像仓库（可选）
echo ""
echo "📦 步骤 1: 构建 Docker 镜像..."
docker compose -f docker-compose.yml build

# 步骤2: 压缩项目文件并上传到服务器
echo ""
echo "📤 步骤 2: 上传项目文件到服务器..."

# 创建临时部署包
DEPLOY_FILE="deploy_${TIMESTAMP}.tar.gz"
tar -czf "/tmp/${DEPLOY_FILE}" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='frontend/dist' \
    --exclude='backend/*.db' \
    docker-compose.yml \
    .env.example \
    backend/ \
    frontend/ \
    deploy/

# SSH 连接并上传
ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=no "root@${SERVER_HOST}" "mkdir -p ${REMOTE_DIR}"
scp -i "${SSH_KEY}" -o StrictHostKeyChecking=no "/tmp/${DEPLOY_FILE}" "root@${SERVER_HOST}:${REMOTE_DIR}/"

# 步骤3: 在服务器上执行部署
echo ""
echo "🚀 步骤 3: 在服务器上执行部署..."
ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=no "root@${SERVER_HOST}" << EOF
    cd ${REMOTE_DIR}

    # 解压部署包
    echo "  解压部署文件..."
    tar -xzf ${DEPLOY_FILE}
    rm ${DEPLOY_FILE}

    # 检查 .env 文件
    if [ ! -f .env ]; then
        echo "  创建 .env 文件..."
        cp .env.example .env
        echo "  ⚠️  请编辑 ${REMOTE_DIR}/.env 文件并填写实际配置"
    fi

    # 安装 Docker Compose v2（如未安装）
    if ! docker compose version &> /dev/null; then
        echo "  安装 Docker Compose v2..."
        apt-get update
        apt-get install -y docker-compose-plugin
    fi

    # 启动 Docker
    echo "  启动 Docker 容器..."
    docker compose down --remove-orphans || true
    docker compose pull || true
    docker compose up -d --build

    # 显示容器状态
    echo ""
    echo "  容器运行状态:"
    docker compose ps

    # 清理旧镜像
    echo ""
    echo "  清理未使用的 Docker 资源..."
    docker system prune -f || true

    echo ""
    echo "✅ 部署完成!"
    echo "  前端地址: http://${SERVER_HOST}"
    echo "  API地址: http://${SERVER_HOST}:8000"
    echo "  API文档: http://${SERVER_HOST}:8000/docs"
EOF

# 清理本地临时文件
rm -f "/tmp/${DEPLOY_FILE}"

echo ""
echo "======================================"
echo "  部署脚本执行完毕"
echo "======================================"
