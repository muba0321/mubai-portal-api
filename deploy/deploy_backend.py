#!/usr/bin/env python3
# ============================================================
# SRE Portal 一键部署脚本 (Python 版)
# 适用于 Windows/Mac/Linux，通过 paramiko SSH 部署
# 用法: python deploy/deploy_backend.py
# ============================================================

import paramiko
import os
import time
import sys

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

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.join(script_dir, ".."))
    compose_src = os.path.join(script_dir, "docker-compose.yml")

    if not os.path.isfile(os.path.join(repo_root, "Dockerfile")):
        err("找不到后端 Dockerfile，请确保脚本在仓库的 deploy/ 目录下")
        sys.exit(1)
    if not os.path.isfile(compose_src):
        err("找不到 docker-compose.yml")
        sys.exit(1)

    log(f"后端源码: {repo_root}")

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
    log("[1/7] 检查 Docker 环境...")
    out, _, rc = run_cmd(client,
        "docker --version 2>/dev/null && docker compose version 2>/dev/null || echo NO_COMPOSE",
        "Docker 和 Docker Compose")

    if "Docker version" not in out:
        warn("Docker 未安装，正在安装...")
        run_cmd(client, "curl -fsSL https://get.docker.com | sh -", "安装 Docker", timeout=300)
        run_cmd(client, "systemctl enable docker && systemctl start docker", "启动 Docker 服务")

    # Step 2: 创建目录
    log("[2/7] 创建项目目录...")
    run_cmd(client, f"mkdir -p {PROJECT_DIR}/frontend {PROJECT_DIR}/backend", "创建目录")

    # Step 3: 获取前端代码（服务器上通过 git clone）
    log("[3/7] 准备前端代码...")
    run_cmd(client,
        f"test -d {PROJECT_DIR}/frontend/.git || git clone {FRONTEND_REPO} {PROJECT_DIR}/frontend",
        "克隆前端仓库")

    # Step 4: 上传后端代码
    log("[4/7] 上传后端代码...")
    sftp = client.open_sftp()
    up, sk = upload_dir_recursive(sftp, repo_root, f"{PROJECT_DIR}/backend")
    log(f"  上传 {up} 个文件，跳过 {sk} 个")

    log("[4/7] 上传 docker-compose.yml...")
    sftp.put(compose_src, f"{PROJECT_DIR}/docker-compose.yml")
    sftp.close()

    # Step 5: 清理旧服务
    log("[5/7] 清理旧服务...")
    run_cmd(client, f"cd {PROJECT_DIR} && docker compose down --remove-orphans 2>/dev/null || true",
            "停止并清理旧服务")
    run_cmd(client, "docker rm -f sre-portal-frontend sre-portal-backend 2>/dev/null || true",
            "强制删除旧容器")

    # Step 6: 构建并启动
    log("[6/7] 构建并启动服务...")
    out, er, rc = run_cmd(client,
        f"cd {PROJECT_DIR} && docker compose build --no-cache 2>&1",
        "构建镜像（约 2-3 分钟）", timeout=600)

    if "failed to solve" in out.lower() or "cannot build" in out.lower():
        err("构建失败")
        print(out[-2000:] if len(out) > 2000 else out)
        client.close()
        sys.exit(1)

    run_cmd(client, f"cd {PROJECT_DIR} && docker compose up -d 2>&1",
            "启动服务")

    # Step 7: 健康检查
    log("[7/7] 等待服务启动并执行健康检查...")
    time.sleep(15)

    out, _, _ = run_cmd(client,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/ 2>/dev/null || echo 000",
        "前端健康检查", timeout=15)
    frontend_code = out.strip().replace("\r", "").replace("\n", "")
    frontend_ok = frontend_code == "200"

    out, _, _ = run_cmd(client,
        "curl -s http://localhost:5000/health 2>/dev/null || echo fail",
        "后端健康检查", timeout=15)
    backend_resp = out.strip().replace("\r", "")
    backend_ok = "ok" in backend_resp.lower()

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
