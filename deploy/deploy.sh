#!/bin/bash
# ============================================================
# SRE Portal Backend 一键部署脚本
# 功能：在远程 VM 上构建并部署 Flask 后端服务
# 数据库和 Nginx/前端不在此脚本中管理
# 用法: bash deploy.sh
# ============================================================

set -e

VM_HOST="154.12.54.207"
VM_USER="root"
PROJECT_DIR="/opt/sre-portal"
BACKEND_DIR="${PROJECT_DIR}/backend"
COMPOSE_FILE="${BACKEND_DIR}/docker-compose.yml"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=============================================="
echo "  SRE Portal Backend 部署"
echo "  目标: ${VM_USER}@${VM_HOST}"
echo "=============================================="

# ----------------------------------------------------------
# Step 1: SSH 到 VM，检查 Docker 环境
# ----------------------------------------------------------
log "[1/6] 检查 Docker 环境..."
ssh ${VM_USER}@${VM_HOST} << 'SSH_EOF'
if command -v docker &> /dev/null; then
    echo "  Docker: $(docker --version)"
else
    echo "  Docker 未安装，正在安装..."
    curl -fsSL https://get.docker.com | sh -
    systemctl enable docker && systemctl start docker
    echo "  Docker 安装完成: $(docker --version)"
fi

if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
    echo "  Docker Compose: 可用"
else
    warn "  docker compose 不可用，尝试安装..."
    DOCKER_CONFIG=/usr/local/lib/docker/cli-plugins
    mkdir -p $DOCKER_CONFIG
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/docker-compose
    chmod +x $DOCKER_CONFIG/docker-compose
    echo "  Docker Compose 安装完成"
fi
SSH_EOF

# ----------------------------------------------------------
# Step 2: 创建项目目录
# ----------------------------------------------------------
log "[2/6] 创建项目目录..."
ssh ${VM_USER}@${VM_HOST} "mkdir -p ${BACKEND_DIR}"

# ----------------------------------------------------------
# Step 3: 上传后端代码
# ----------------------------------------------------------
log "[3/6] 上传后端代码到 ${BACKEND_DIR}..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_SRC="$(cd "${SCRIPT_DIR}/../../02-backend/sre-portal-backend" && pwd)"

if [ ! -f "${BACKEND_SRC}/Dockerfile" ]; then
    err "找不到后端源码目录: ${BACKEND_SRC}"
    err "请确保项目结构正确: 04-deploy/deploy.sh"
    exit 1
fi

# 同步代码 (排除不必要文件)
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude '.git' \
    --exclude '.DS_Store' \
    "${BACKEND_SRC}/" ${VM_USER}@${VM_HOST}:${BACKEND_DIR}/

log "代码上传完成"

# ----------------------------------------------------------
# Step 4: 上传 docker-compose.yml
# ----------------------------------------------------------
log "[4/6] 上传 docker-compose.yml..."
COMPOSE_SRC="$(cd "${SCRIPT_DIR}" && pwd)/backend-docker-compose.yml"

if [ -f "${COMPOSE_SRC}" ]; then
    scp "${COMPOSE_SRC}" ${VM_USER}@${VM_HOST}:${COMPOSE_FILE}
else
    # 使用默认配置
    ssh ${VM_USER}@${VM_HOST} << COMPOSE_EOF
cat > ${COMPOSE_FILE} << 'EOF'
version: '3.8'

services:
  sre-portal-backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: sre-portal-backend
    restart: always
    environment:
      FLASK_ENV: \${FLASK_ENV:-production}
      DATABASE_URL: \${DATABASE_URL:-mysql+pymysql://root:huanxin0321@154.12.54.207:3306/sre_portal}
      SECRET_KEY: \${SECRET_KEY:-change-me-in-production}
      JWT_SECRET_KEY: \${JWT_SECRET_KEY:-change-me-in-production}
      JWT_EXPIRES: \${JWT_EXPIRES:-3600}
      JWT_REFRESH_EXPIRES: \${JWT_REFRESH_EXPIRES:-604800}
    ports:
      - "5000:5000"
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
COMPOSE_EOF
COMPOSE_FILE
fi

# ----------------------------------------------------------
# Step 5: 构建并启动
# ----------------------------------------------------------
log "[5/6] 构建并启动后端服务..."
ssh ${VM_USER}@${VM_HOST} << SSH_EOF
cd ${BACKEND_DIR}

# 停止旧服务
echo "  停止旧服务..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true

# 构建镜像
echo "  构建 Docker 镜像..."
docker compose build 2>/dev/null || docker-compose build 2>/dev/null

# 启动服务
echo "  启动服务..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null
SSH_EOF

# ----------------------------------------------------------
# Step 6: 健康检查
# ----------------------------------------------------------
log "[6/6] 等待服务启动并执行健康检查..."
sleep 10

MAX_RETRIES=12
RETRY=0
HEALTHY=false

while [ $RETRY -lt $MAX_RETRIES ]; do
    STATUS=$(ssh ${VM_USER}@${VM_HOST} "docker inspect --format='{{.State.Health.Status}}' sre-portal-backend 2>/dev/null || echo 'unknown'")
    if [ "$STATUS" = "healthy" ]; then
        HEALTHY=true
        break
    fi
    RETRY=$((RETRY + 1))
    log "  等待中... ($RETRY/$MAX_RETRIES) 状态: $STATUS"
    sleep 10
done

echo ""
ssh ${VM_USER}@${VM_HOST} "docker ps --filter name=sre-portal-backend --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo ""

if [ "$HEALTHY" = true ]; then
    log "后端服务部署成功！"
    echo "=============================================="
    log "API 地址: http://${VM_HOST}:5000"
    log "健康检查: http://${VM_HOST}:5000/health"
    log "查看日志: ssh ${VM_USER}@${VM_HOST} 'docker logs -f sre-portal-backend'"
    echo "=============================================="
else
    warn "服务已启动但健康检查未通过，请查看日志："
    ssh ${VM_USER}@${VM_HOST} "docker logs --tail 50 sre-portal-backend"
    echo ""
    err "部署可能有问题，请检查上述日志"
    exit 1
fi
