#!/usr/bin/env python3
# ============================================================
# SRE Portal Backend 一键部署脚本 (Python 版)
# 适用于 Windows/Mac/Linux，通过 paramiko SSH 部署
# 用法: python deploy_backend.py
# ============================================================

import paramiko
import os
import time
import sys

HOST = "154.12.54.207"
USER = "root"
PASSWORD = os.getenv("VM_PASSWORD", "Huanxin0321")
PROJECT_DIR = "/opt/sre-portal"
BACKEND_DIR = f"{PROJECT_DIR}/backend"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

def log(msg): print(f"{GREEN}[INFO]{NC} {msg}")
def warn(msg): print(f"{YELLOW}[WARN]{NC} {msg}")
def err(msg): print(f"{RED}[ERROR]{NC} {msg}")

def resolve_backend_src():
    """自动定位后端源码目录"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "..", "02-backend", "sre-portal-backend"),
        os.path.join(script_dir, "..", "..", "02-backend", "sre-portal-backend"),
        os.path.join(script_dir, "sre-portal-backend"),
    ]
    for c in candidates:
        abs_c = os.path.normpath(c)
        if os.path.isfile(os.path.join(abs_c, "Dockerfile")):
            return abs_c
    return None

def upload_dir_recursive(client, local_dir, remote_dir):
    """通过 sftp 上传整个目录"""
    sftp = client.open_sftp()
    uploaded = 0
    skipped = 0

    def _upload(local, remote):
        nonlocal uploaded, skipped
        try:
            sftp.stat(remote)
        except FileNotFoundError:
            sftp.mkdir(remote)

        for item in os.listdir(local):
            if item in ("__pycache__", ".venv", "venv", ".git", "node_modules"):
                skipped += 1
                continue
            if item.endswith((".pyc", ".pyo", ".DS_Store")):
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
    sftp.close()
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
        for line in out.strip().split("\n")[-10:]:  # 只显示最后10行
            print(f"    {line}")
    if er.strip() and rc != 0:
        for line in er.strip().split("\n")[-10:]:
            print(f"    [stderr] {line}")
    return out, er, rc

def main():
    print("=" * 50)
    print("  SRE Portal Backend 部署")
    print(f"  目标: {USER}@{HOST}")
    print("=" * 50)

    # 定位源码
    src_dir = resolve_backend_src()
    if not src_dir:
        err("找不到后端源码目录，请确保 02-backend/sre-portal-backend 存在")
        sys.exit(1)
    log(f"源码目录: {src_dir}")

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
    log("[1/5] 检查 Docker 环境...")
    out, _, rc = run_cmd(client,
        "docker --version 2>/dev/null && docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo NO_COMPOSE",
        "Docker 和 Docker Compose")

    if "Docker version" not in out:
        warn("Docker 未安装，正在安装...")
        run_cmd(client, "curl -fsSL https://get.docker.com | sh -", "安装 Docker", timeout=300)
        run_cmd(client, "systemctl enable docker && systemctl start docker", "启动 Docker 服务")
        run_cmd(client, "docker --version", "验证 Docker")

    # Step 2: 创建目录
    log("[2/5] 创建项目目录...")
    run_cmd(client, f"mkdir -p {BACKEND_DIR}", "创建目录")

    # Step 3: 上传代码
    log("[3/5] 上传后端代码...")
    uploaded, skipped = upload_dir_recursive(client, src_dir, BACKEND_DIR)
    log(f"上传 {uploaded} 个文件，跳过 {skipped} 个")

    # Step 4: 构建并启动
    log("[4/5] 构建并启动服务...")
    run_cmd(client, f"cd {BACKEND_DIR} && docker rm -f sre-portal-backend 2>/dev/null; docker compose down --remove-orphans 2>/dev/null || true",
            "停止并清理旧服务")

    out, er, rc = run_cmd(client, f"cd {BACKEND_DIR} && docker compose build --no-cache 2>&1 || docker-compose build --no-cache 2>&1",
                          "构建镜像", timeout=600)

    if "error" in out.lower() or rc != 0:
        err("构建失败，查看完整输出:")
        print(out[-2000:] if len(out) > 2000 else out)
        client.close()
        sys.exit(1)

    run_cmd(client, f"cd {BACKEND_DIR} && docker compose up -d 2>&1 || docker-compose up -d 2>&1",
            "启动服务")

    # Step 5: 健康检查
    log("[5/5] 等待服务启动并执行健康检查...")
    time.sleep(10)

    max_retries = 12
    healthy = False
    for i in range(max_retries):
        out, _, _ = run_cmd(client,
            "docker inspect --format='{{.State.Health.Status}}' sre-portal-backend 2>/dev/null || echo unknown",
            f"健康检查 ({i+1}/{max_retries})")
        status = out.strip()
        if status == "healthy":
            healthy = True
            break
        time.sleep(10)

    print()
    run_cmd(client, "docker ps --filter name=sre-portal-backend --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
            "容器状态")
    print()

    client.close()

    if healthy:
        log("后端服务部署成功！")
        print("=" * 50)
        log(f"API 地址: http://{HOST}:5000")
        log(f"健康检查: http://{HOST}:5000/health")
        log(f"查看日志: ssh {USER}@{HOST} 'docker logs -f sre-portal-backend'")
        print("=" * 50)
    else:
        warn("服务已启动但健康检查未通过，查看最近日志:")
        c2 = paramiko.SSHClient()
        c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c2.connect(HOST, username=USER, password=PASSWORD, timeout=20)
        out, _, _ = run_cmd(c2, "docker logs --tail 30 sre-portal-backend", "最近30行日志")
        c2.close()
        print()
        err("部署可能有问题，请检查上述日志")
        sys.exit(1)

if __name__ == "__main__":
    main()
