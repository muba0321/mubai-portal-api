# SRE Portal 部署文档

## 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [部署流程](#部署流程)
- [版本发布](#版本发布)
- [常用命令](#常用命令)
- [故障排查](#故障排查)

---

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker | >= 20.10 | 容器运行时 |
| Docker Compose | >= 2.0 | 服务编排 |
| Git | >= 2.0 | 代码管理 |
| MySQL | >= 8.0 | 数据库（已部署在 154.12.54.207） |

---

## 快速开始

### 首次部署

```bash
# 1. 克隆后端仓库
git clone https://github.com/muba0321/mubai-portal-api.git
cd mubai-portal-api

# 2. 克隆前端仓库（与后端仓库同级目录）
cd ..
git clone https://github.com/muba0321/mubai-portal.git

# 3. 进入后端目录，配置环境变量
cd mubai-portal-api
cp .env.production.example .env
vi .env  # 修改 SECRET_KEY、JWT_SECRET_KEY 等

# 4. 一键部署
chmod +x deploy.sh
./deploy.sh
```

### 更新部署

```bash
cd mubai-portal-api
./deploy.sh v1.1.0   # 指定版本部署
# 或
./deploy.sh          # 部署当前分支最新代码
```

---

## 配置说明

### .env 配置项

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `DATABASE_URL` | 是 | 数据库连接串 | `mysql+pymysql://root:pass@host:3306/db` |
| `SECRET_KEY` | 是 | Flask 密钥 | 随机字符串 |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥 | 随机字符串 |
| `JWT_EXPIRES` | 否 | Access Token 过期时间（秒） | `3600` |
| `JWT_REFRESH_EXPIRES` | 否 | Refresh Token 过期时间（秒） | `604800` |
| `IMAGE_TAG` | 否 | Docker 镜像标签 | `v1.0.0` |

> **安全提示**: 生产环境务必修改 `SECRET_KEY` 和 `JWT_SECRET_KEY`，建议使用至少 32 位随机字符串。

### docker-compose.yml 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| `sre-portal-backend` | 5000 | Flask API 服务 |
| `sre-portal-nginx` | 80 | Nginx（前端静态资源 + API 反向代理） |

---

## 部署流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  前端代码    │────▶│  Docker     │────▶│  Nginx      │
│  (Vue3)     │     │  镜像构建   │     │  (端口 80)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐     ┌─────────────┐     ┌──────▼──────┐
│  后端代码    │────▶│  Docker     │────▶│  Flask API  │
│  (Flask)    │     │  镜像构建   │     │  (端口 5000) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐                                │
│  MySQL      │◀───────────────────────────────┘
│  数据库     │
└─────────────┘
```

1. **前端构建** — pnpm build → 静态文件打包到 nginx 镜像
2. **后端构建** — 安装依赖 → 打包 Flask + gunicorn 镜像
3. **数据库迁移** — 自动执行 Alembic migration
4. **服务启动** — docker-compose 启动所有容器

---

## 版本发布

### 发布新版本

```bash
# 1. 更新版本号
# 前端: package.json version 字段
# 后端: app/config.py APP_VERSION + VERSION 文件

# 2. 更新 CHANGELOG.md
# 记录本次版本的变更内容

# 3. 提交并打标签
git add .
git commit -m "chore: release v1.1.0"
git tag v1.1.0

# 4. 推送
git push origin main v1.1.0

# 5. 部署
./deploy.sh v1.1.0
```

### 数据库迁移

每次数据库表结构变更后：

```bash
# 本地生成迁移脚本
flask db migrate -m "描述变更内容"

# 部署时自动执行（deploy.sh 已包含）
# 或手动执行
docker compose run --rm sre-portal-backend flask db upgrade
```

---

## 常用命令

```bash
# 查看所有服务状态
docker compose ps

# 查看日志
docker compose logs -f                    # 所有服务
docker compose logs -f sre-portal-backend # 仅后端
docker compose logs -f sre-portal-nginx   # 仅 Nginx

# 重启服务
docker compose restart sre-portal-backend
docker compose restart sre-portal-nginx

# 停止服务
docker compose down

# 停止并删除数据卷
docker compose down -v

# 进入容器
docker compose exec sre-portal-backend bash
docker compose exec sre-portal-nginx sh

# 手动执行数据库迁移
docker compose exec sre-portal-backend flask db upgrade

# 查看后端健康状态
curl http://localhost:5000/health
```

---

## 故障排查

### 后端无法连接数据库

```bash
# 检查数据库连接
docker compose exec sre-portal-backend python -c "
from app import create_app
from app.extensions import db
app = create_app('production')
with app.app_context():
    db.engine.connect()
    print('数据库连接成功')
"
```

### 前端页面空白

```bash
# 检查 Nginx 配置
docker compose exec sre-portal-nginx nginx -t

# 检查静态文件是否存在
docker compose exec sre-portal-nginx ls -la /usr/share/nginx/html/
```

### 查看容器资源占用

```bash
docker stats sre-portal-backend sre-portal-nginx
```

### 镜像构建失败

```bash
# 清理缓存重新构建
docker compose build --no-cache
```
