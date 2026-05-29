# SRE Portal 部署文档

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker | >= 20.10 | 容器运行时 |
| Docker Compose | >= 2.0 | 服务编排 |
| Python | >= 3.9 | 部署脚本运行环境 |
| paramiko | >= 3.0 | SSH 连接库 |

## 一键部署

```bash
# 安装依赖
pip install paramiko

# 执行部署（Windows/Mac/Linux 均可）
python deploy/deploy_backend.py
```

脚本自动完成：
1. SSH 连接到服务器
2. 检查 Docker 环境（未安装则自动安装）
3. 从 GitHub 克隆前端代码（仅首次）
4. 上传后端代码和 docker-compose.yml
5. 停止旧服务、构建新镜像、启动新容器
6. 健康检查确认前后端都正常运行

## 手动部署

```bash
# 1. SSH 到服务器
ssh root@154.12.54.207

# 2. 更新前端代码
cd /opt/sre-portal/frontend
git pull

# 3. 构建并重启
cd /opt/sre-portal
docker compose build --no-cache
docker compose up -d
```

## 服务器架构

```
┌─────────────────────────────────────────────┐
│         154.12.54.207 (VM)                  │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ sre-portal-frontend : 3000          │   │
│  │ (nginx:alpine — 静态文件 + API代理) │   │
│  └──────────────────┬──────────────────┘   │
│                     │ Docker 网络            │
│  ┌──────────────────▼──────────────────┐   │
│  │ sre-portal-backend : 5000           │   │
│  │ (Flask + Gunicorn)                  │   │
│  └──────────────────┬──────────────────┘   │
│                     │                        │
│  ┌──────────────────▼──────────────────┐   │
│  │ sre-portal-mysql : 3306             │   │
│  │ (MySQL 8.0)                          │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## 常用命令

```bash
# 查看容器状态
ssh root@154.12.54.207 'cd /opt/sre-portal && docker compose ps'

# 查看日志
ssh root@154.12.54.207 'cd /opt/sre-portal && docker compose logs -f'

# 查看后端健康状态
curl http://154.12.54.207:5000/health

# 进入容器
ssh root@154.12.54.207 'docker exec -it sre-portal-backend bash'

# 手动执行数据库迁移
ssh root@154.12.54.207 'docker exec sre-portal-backend flask db upgrade'
```

## 故障排查

### 前端页面空白
```bash
# 检查 nginx 容器日志
ssh root@154.12.54.207 'docker logs sre-portal-frontend'

# 验证 API 代理是否正常
ssh root@154.12.54.207 'curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/v1/auth/login -X POST'
```

### 后端健康检查失败
```bash
# 查看后端日志
ssh root@154.12.54.207 'docker logs sre-portal-backend'

# 检查数据库连接
ssh root@154.12.54.207 'docker exec sre-portal-backend python -c "from app import create_app; app = create_app(\"production\"); print(\"DB OK\")"'
```

### 构建失败
```bash
# 清理缓存重新构建
ssh root@154.12.54.207 'cd /opt/sre-portal && docker builder prune -af && docker compose build --no-cache'
```

## 历史问题记录

完整的问题解决记录见 [docs/deploy-issues-summary.html](docs/deploy-issues-summary.html)
