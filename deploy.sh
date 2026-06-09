#!/bin/bash

# 股票分析系统部署脚本
# 使用方法：
#   ./deploy.sh backend    # 只部署后端
#   ./deploy.sh frontend   # 只部署前端
#   ./deploy.sh all        # 部署所有服务
#   ./deploy.sh reload     # 优雅重启（不重新构建）

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否运行
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker未运行，请先启动Docker"
        exit 1
    fi
}

# 优雅重启后端（避免502）
reload_backend() {
    log_info "开始优雅重启后端..."
    
    # 1. 重新构建后端镜像
    log_info "重新构建后端镜像..."
    docker compose build backend
    
    # 2. 创建新的后端容器（不立即启动）
    log_info "创建新的后端容器..."
    docker compose up -d --no-deps --build backend
    
    # 3. 等待后端健康检查通过
    log_info "等待后端服务就绪..."
    attempts=0
    max_attempts=30
    
    while [ $attempts -lt $max_attempts ]; do
        if docker inspect --format='{{.State.Health.Status}}' stock-backend 2>/dev/null | grep -q "healthy"; then
            log_info "✅ 后端服务已就绪"
            break
        fi
        
        attempts=$((attempts + 1))
        log_warn "等待后端启动... ($attempts/$max_attempts)"
        sleep 2
    done
    
    if [ $attempts -eq $max_attempts ]; then
        log_error "后端服务启动超时，请检查日志: docker compose logs backend"
        exit 1
    fi
    
    # 4. 重新加载前端nginx配置（可选）
    log_info "重新加载前端配置..."
    docker exec stock-frontend nginx -s reload 2>/dev/null || true
    
    log_info "✅ 后端重启完成"
}

# 部署后端
deploy_backend() {
    log_info "开始部署后端..."
    check_docker
    
    # 重新构建并启动
    docker compose up -d --build backend
    
    # 等待健康检查
    reload_backend
    
    log_info "✅ 后端部署完成"
}

# 部署前端
deploy_frontend() {
    log_info "开始部署前端..."
    check_docker
    
    # 重新构建并启动
    docker compose up -d --build frontend
    
    # 等待前端就绪
    log_info "等待前端服务就绪..."
    sleep 5
    
    log_info "✅ 前端部署完成"
}

# 部署所有服务
deploy_all() {
    log_info "开始部署所有服务..."
    check_docker
    
    # 重新构建所有服务
    docker compose up -d --build
    
    # 等待服务就绪
    log_info "等待服务就绪..."
    sleep 10
    
    # 检查服务状态
    docker compose ps
    
    log_info "✅ 所有服务部署完成"
    log_info "访问地址: http://localhost"
}

# 优雅重启（不重新构建）
reload_services() {
    log_info "开始优雅重启服务..."
    check_docker
    
    # 重启后端
    reload_backend
    
    # 重启前端
    log_info "重启前端..."
    docker compose restart frontend
    sleep 3
    
    log_info "✅ 服务重启完成"
}

# 查看服务状态
status() {
    log_info "服务状态:"
    docker compose ps
    
    echo ""
    log_info "健康检查状态:"
    docker inspect --format='{{.Name}}: {{.State.Health.Status}}' stock-backend stock-frontend 2>/dev/null || true
}

# 查看日志
logs() {
    service=${1:-all}
    if [ "$service" = "all" ]; then
        docker compose logs -f --tail=100
    else
        docker compose logs -f --tail=100 $service
    fi
}

# 清理旧镜像
cleanup() {
    log_info "清理旧镜像..."
    docker image prune -f
    log_info "✅ 清理完成"
}

# 主函数
main() {
    case "${1:-all}" in
        backend)
            deploy_backend
            ;;
        frontend)
            deploy_frontend
            ;;
        all)
            deploy_all
            ;;
        reload)
            reload_services
            ;;
        status)
            status
            ;;
        logs)
            logs ${2:-all}
            ;;
        cleanup)
            cleanup
            ;;
        *)
            echo "使用方法: $0 {backend|frontend|all|reload|status|logs|cleanup}"
            echo ""
            echo "命令说明:"
            echo "  backend  - 只部署后端"
            echo "  frontend - 只部署前端"
            echo "  all      - 部署所有服务（默认）"
            echo "  reload   - 优雅重启（不重新构建）"
            echo "  status   - 查看服务状态"
            echo "  logs     - 查看日志"
            echo "  cleanup  - 清理旧镜像"
            exit 1
            ;;
    esac
}

main "$@"
