# SRE Portal — 后端服务

Flask API 后端 + 部署脚本 + 数据库初始化脚本。

## 仓库结构

```
├── app/                 # Flask 应用源码
├── migrations/          # Alembic 数据库迁移
├── deploy/              # 生产部署相关文件
│   ├── deploy_backend.py  # Python 一键部署脚本
│   ├── deploy.sh          # Bash 一键部署脚本
│   ├── docker-compose.yml # 服务器编排文件
│   └── init.sql           # 数据库初始化脚本
├── database/            # 数据库相关配置
├── docs/                # 部署文档和问题总结
├── Dockerfile           # 后端 Docker 镜像
├── docker-compose.yml   # 本地开发编排（仅后端）
├── .env.production.example
├── DEPLOY.md            # 详细部署文档
└── CHANGELOG.md
```

## 快速部署

```bash
# 1. 克隆仓库
git clone https://github.com/muba0321/mubai-portal-api.git
cd mubai-portal-api

# 2. 一键部署（需要 Python 3 + paramiko）
pip install paramiko
python deploy/deploy_backend.py
```

> 部署脚本会自动从 GitHub 拉取前端代码，构建前后端完整服务。
> 详细说明见 [DEPLOY.md](DEPLOY.md)

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务
python run.py
```

## 相关仓库

| 仓库 | 说明 |
|------|------|
| [muba0321/mubai-portal](https://github.com/muba0321/mubai-portal) | 前端 (Vue 3 + Vite) |
