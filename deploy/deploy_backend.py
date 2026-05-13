#!/usr/bin/env python3
# ============================================================
# SRE Portal 一键部署脚本 (Python 版)
# 适用于 Windows/Mac/Linux，通过 paramiko SSH 部署
# 用途：部署前后端完整服务（前端 + 后端 + MySQL 已存在）
# 用法: python deploy/deploy_backend.py
# ============================================================

import paramiko
import os
import time
import sys
import subprocess

HOST = "154.12.54.207"
USER = "root"
PASSWORD = os.getenv("VM_PASSWORD", "Huanxin0321")
PROJECT_DIR = "/opt/sre-portal"
FRONTEND_REPO = "https://github.com/muba0321/mubai-portal.git"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

def log(msg): print(f"{GREEN}[INFO]{NC} {msg}")
def warn(msg): print(f"{YELLOW}[WARN]{NC} {msg}")
def err(msg): print(f"{RED}[ERROR]{NC} {msg}")

def resolve_project_root():
    """自动定位项目根目录（04-deploy 的上一级）"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, ".."),
        os.path.join(script_dir, "..", ".."),
    ]
    for c in candidates:
        abs_c = os.path.normpath(c)
        frontend = os.path.join(abs_c, "01-frontend", "sre-portal-frontend", "Dockerfile")
        backend = os.path.join(abs_c, "02-backend", "sre-portal-backend", "Dockerfile")
        if os.path.isfile(frontend) and os.path.isfile(backend):
            return abs_c
    return None

def upload_dir_recursive(sftp, local_dir, remote_dir, exclude_dirs=None, exclude_exts=None):
    """通过 sftp 上传整个目录"""
    if exclude_dirs is None:
        exclude_dirs = ("__pycache__", ".venv", "venv", ".git", "node_modules")
    if exclude_exts is None:
        exclude_exts = (".pyc", ".pyo", ".DS_Store")

    uploaded = 0
    skipped = 0

    def _upload(local, remote):
        nonlocal uploaded, skipped
        try:
            sftp.stat(remote)
        except FileNotFoundError:
            sftp.mkdir(remote)

        for item in os.listdir(local):
            if item in exclude_dirs:
                skipped += 1
                continue
            if item.endswith(exclude_exts):
                skipped += 1
                continue

            lp = os.path.join(local, item)
            rp = f"{remote}/{item}"
            if os.path.isdir(lp):
                try:
                    sftp.stat(rp)
                except FileNotFoundError:
                    sftp.mkdir(rp)
                _upload(lp, rp)
            else:
                sftp.put(lp, rp)
                uploaded += 1

    _upload(local_dir, remote_dir)
    return uploaded, skipped

def run_cmd(client, cmd, desc="", timeout=120):
    """执行远程命令并返回输出"""
    if desc:
        print(f"  {desc}")
    print(f"    $ {cmd[:90]}{'...' if len(cmd) > 90 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    er = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        for line in out.strip().split("\n")[-10:]:
            print(f"    {line}")
    if er.strip() and rc != 0:
        for line in er.strip().split("\n")[-10:]:
            print(f"    [stderr] {line}")
    return out, er, rc

def main():
    print("=" * 50)
    print("  SRE Portal 一键部署（前端 + 后端）")
    print(f"  目标: {USER}@{HOST}")
    print("=" * 50)

    # 定位项目根目录
    project_root = resolve_project_root()
    if not project_root:
        err("找不到项目根目录，请确保：")
        print("  1. 此脚本在 04-deploy/ 目录下")
        print("  2. 项目结构包含 01-frontend/ 和 02-backend/")
        sys.exit(1)

    frontend_src = os.path.join(project_root, "01-frontend", "sre-portal-frontend")
    backend_src = os.path.join(project_root, "02-backend", "sre-portal-backend")
    compose_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docker-compose.yml")

    log(f"前端源码: {frontend_src}")
    log(f"后端源码: {backend_src}")

    # SSH 连接
    log(f"连接 SSH {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, username=USER, password=PASSWORD, timeout=20)
    except paramiko.AuthenticationException:
        err("SSH 认证失败，请检查密码或设置 VM_PASSWORD 环境变量")
        sys.exit(1)
    except Exception as e:
        err(f"SSH 连接失败: {e}")
        sys.exit(1)
    log("SSH 已连接")

    # Step 1: 检查 Docker
    log("[1/6] 检查 Docker 环境...")
    out, _, rc = run_cmd(client,
        "docker --version 2>/dev/null && docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo NO_COMPOSE",
        "Docker 和 Docker Compose")

    if "Docker version" not in out:
        warn("Docker 未安装，正在安装...")
        run_cmd(client, "curl -fsSL https://get.docker.com | sh -", "安装 Docker", timeout=300)
        run_cmd(client, "systemctl enable docker && systemctl start docker", "启动 Docker 服务")
        run_cmd(client, "docker --version", "验证 Docker")

    # Step 2: 创建目录
    log("[2/6] 创建项目目录...")
    run_cmd(client, f"mkdir -p {PROJECT_DIR}/frontend {PROJECT_DIR}/backend", "创建目录")

    # Step 3: 上传源码
    sftp = client.open_sftp()

    log("[3/6] 上传前端代码...")
    up, sk = upload_dir_recursive(sftp, frontend_src, f"{PROJECT_DIR}/frontend")
    log(f"  上传 {up} 个文件，跳过 {sk} 个")

    log("[3/6] 上传后端代码...")
    up, sk = upload_dir_recursive(sftp, backend_src, f"{PROJECT_DIR}/backend")
    log(f"  上传 {up} 个文件，跳过 {sk} 个")

    log("[3/6] 上传 docker-compose.yml...")
    sftp.put(compose_src, f"{PROJECT_DIR}/docker-compose.yml")
    sftp.close()

    # Step 4: 清理旧服务
    log("[4/6] 清理旧服务...")
    run_cmd(client, f"cd {PROJECT_DIR} && docker compose down --remove-orphans 2>/dev/null || true",
            "停止并清理旧服务")
    run_cmd(client, "docker rm -f sre-portal-frontend sre-portal-backend 2>/dev/null || true",
            "强制删除旧容器")

    # Step 5: 构建并启动
    log("[5/6] 构建并启动服务（前端 + 后端）...")
    out, er, rc = run_cmd(client,
        f"cd {PROJECT_DIR} && docker compose build --no-cache 2>&1",
        "构建镜像（约 2-3 分钟）", timeout=600)

    if "error" in out.lower() and "failed to solve" in out.lower():
        err("构建失败，查看完整输出:")
        print(out[-2000:] if len(out) > 2000 else out)
        client.close()
        sys.exit(1)

    run_cmd(client, f"cd {PROJECT_DIR} && docker compose up -d 2>&1",
            "启动服务")

    # Step 6: 健康检查
    log("[6/6] 等待服务启动并执行健康检查...")
    time.sleep(15)

    # 检查前端
    _, out, _ = run_cmd(client,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/ 2>/dev/null || echo 000",
        "前端健康检查", timeout=15)
    frontend_ok = out.strip() == "200"

    # 检查后端
    _, out, _ = run_cmd(client,
        "curl -s http://localhost:5000/health 2>/dev/null || echo fail",
        "后端健康检查", timeout=15)
    backend_ok = "ok" in out.lower()

    print()
    run_cmd(client, f"cd {PROJECT_DIR} && docker compose ps", "容器状态")
    print()

    client.close()

    if frontend_ok and backend_ok:
        log("部署成功！")
        print("=" * 50)
        log(f"前端: http://{HOST}:3000")
        log(f"后端: http://{HOST}:5000")
        log(f"健康: http://{HOST}:5000/health")
        log(f"查看日志: ssh {USER}@{HOST} 'cd {PROJECT_DIR} && docker compose logs -f'")
        print("=" * 50)
    else:
        if not frontend_ok:
            warn("前端服务异常")
        if not backend_ok:
            warn("后端服务异常")
        err("请检查上述日志")
        sys.exit(1)

if __name__ == "__main__":
    main()
