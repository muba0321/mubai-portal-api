#!/bin/bash
##############################################################################
# SRE Portal 一键部署脚本
# 用法: ./deploy.sh [version]
#   version: 可选，指定要部署的版本 tag（如 v1.0.0），默认部署当前分支最新代码
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 加载 .env 配置
if [ -f .env ]; then
    info "加载 .env 配置文件"
    export $(grep -v '^#' .env | xargs)
else
    warn ".env 文件不存在，使用 docker-compose.yml 中的默认配置"
    if [ ! -f .env.production.example ]; then
        error "请复制 .env.production.example 为 .env 并配置后重新运行"
    fi
fi

IMAGE_TAG="${IMAGE_TAG:-latest}"
VERSION="$1"

##############################################################################
# 1. 拉取最新代码
##############################################################################
info "=== 步骤 1/5: 拉取最新代码 ==="
if [ -n "$VERSION" ]; then
    info "检出版本: $VERSION"
    git fetch --tags
    git checkout "$VERSION" || error "版本 $VERSION 不存在"
else
    info "拉取当前分支最新代码"
    git pull || warn "git pull 失败，继续使用本地代码"
fi

##############################################################################
# 2. 构建前端镜像
##############################################################################
info "=== 步骤 2/5: 构建前端镜像 ==="
FRONTEND_DIR="../01-frontend/mubai-portal"
if [ ! -d "$FRONTEND_DIR" ]; then
    error "前端代码目录不存在: $FRONTEND_DIR"
fi

docker build \
    -t sre-portal-frontend:${IMAGE_TAG} \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    "$FRONTEND_DIR" || error "前端镜像构建失败"
info "前端镜像构建完成: sre-portal-frontend:${IMAGE_TAG}"

##############################################################################
# 3. 构建后端镜像
##############################################################################
info "=== 步骤 3/5: 构建后端镜像 ==="
docker build \
    -t sre-portal-backend:${IMAGE_TAG} \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    . || error "后端镜像构建失败"
info "后端镜像构建完成: sre-portal-backend:${IMAGE_TAG}"

##############################################################################
# 4. 数据库迁移
##############################################################################
info "=== 步骤 4/5: 执行数据库迁移 ==="
docker compose run --rm sre-portal-backend python -c "
from app import create_app
from app.extensions import db, migrate
from flask_migrate import upgrade

app = create_app('production')
with app.app_context():
    upgrade()
    print('数据库迁移完成')
" || warn "数据库迁移失败，请检查数据库连接配置"

##############################################################################
# 5. 启动服务
##############################################################################
info "=== 步骤 5/5: 启动服务 ==="
docker compose down --remove-orphans
docker compose up -d

# 等待服务启动
info "等待服务启动..."
sleep 5

# 健康检查
info "检查后端健康状态..."
MAX_RETRIES=10
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
        info "后端服务健康检查通过"
        break
    fi
    RETRY=$((RETRY + 1))
    sleep 3
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    warn "后端健康检查超时，请查看日志: docker compose logs sre-portal-backend"
fi

##############################################################################
# 完成
##############################################################################
info "========================================="
info "部署完成！"
info "========================================="
info "前端地址: http://$(hostname -I | awk '{print $1}')"
info "后端地址: http://$(hostname -I | awk '{print $1}'):5000"
info ""
info "常用命令:"
info "  查看日志:    docker compose logs -f"
info "  停止服务:    docker compose down"
info "  重启服务:    docker compose restart"
info "  查看状态:    docker compose ps"
