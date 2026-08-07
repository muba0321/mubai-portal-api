#!/bin/bash
# 容器启动后初始化脚本
# 用于复制 SSH 密钥等必要文件到容器内

set -e

echo "=== 复制 SSH 密钥 ==="
if [ -f /root/.ssh/sre_portal_key ]; then
    docker exec sre-portal-backend mkdir -p /root/.ssh
    docker cp /root/.ssh/sre_portal_key sre-portal-backend:/root/.ssh/sre_portal_key
    docker cp /root/.ssh/sre_portal_key.pub sre-portal-backend:/root/.ssh/sre_portal_key.pub
    docker exec sre-portal-backend chmod 600 /root/.ssh/sre_portal_key
    docker exec sre-portal-backend chmod 644 /root/.ssh/sre_portal_key.pub
    echo "SSH 密钥已复制"
else
    echo "警告: SSH 密钥不存在 (/root/.ssh/sre_portal_key)"
fi

echo ""
echo "=== 验证 SSH 连接 ==="
docker exec sre-portal-backend ssh -o StrictHostKeyChecking=no -i /root/.ssh/sre_portal_key root@154.201.73.215 "echo 'SSH 连接正常'" || echo "SSH 连接失败"

echo ""
echo "初始化完成"
