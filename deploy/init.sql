-- SRE Portal 数据库初始化脚本
-- 数据库: sre_portal
-- 创建时间: 2026-05-11

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `sre_portal` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `sre_portal`;

-- =============================================
-- 1. CMDB 虚拟机表
-- =============================================
DROP TABLE IF EXISTS `cmdb_vm`;
CREATE TABLE `cmdb_vm` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `name` VARCHAR(100) NOT NULL COMMENT '虚拟机名称',
    `cluster` VARCHAR(100) NOT NULL COMMENT '所属集群',
    `external_ip` VARCHAR(45) NOT NULL COMMENT '外部 IP 地址',
    `internal_ip` VARCHAR(45) NOT NULL COMMENT '内部 IP 地址',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '描述说明',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态（1=在线, 0=离线）',
    `tenant` VARCHAR(100) NOT NULL COMMENT '所属租户',
    `vcpus` INT NOT NULL DEFAULT 4 COMMENT 'CPU 核数',
    `memory` INT NOT NULL DEFAULT 8192 COMMENT '内存（MB）',
    `disk` VARCHAR(50) DEFAULT NULL COMMENT '硬盘容量',
    `access_url` VARCHAR(500) DEFAULT NULL COMMENT '访问地址',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    `updated_by` VARCHAR(64) DEFAULT NULL COMMENT '更新人',
    `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除（0=未删, 1=已删）',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_name_deleted` (`name`, `deleted`),
    KEY `idx_cluster` (`cluster`),
    KEY `idx_tenant` (`tenant`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='CMDB 虚拟机资产表';

-- =============================================
-- 2. 系统状态快照表
-- =============================================
DROP TABLE IF EXISTS `sys_monitor`;
CREATE TABLE `sys_monitor` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `server_online` INT NOT NULL DEFAULT 0 COMMENT '在线服务器数',
    `service_running` INT NOT NULL DEFAULT 0 COMMENT '运行中服务数',
    `network_status` VARCHAR(20) NOT NULL DEFAULT 'normal' COMMENT '网络状态（normal/abnormal）',
    `storage_usage` VARCHAR(20) DEFAULT NULL COMMENT '存储使用率',
    `alert_pending` INT NOT NULL DEFAULT 0 COMMENT '未处理告警数',
    `cpu_load` VARCHAR(20) DEFAULT NULL COMMENT 'CPU 负载',
    `snapshot_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '快照时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统状态快照表';

-- =============================================
-- 3. 常用链接配置表
-- =============================================
DROP TABLE IF EXISTS `sys_common_link`;
CREATE TABLE `sys_common_link` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `title` VARCHAR(100) NOT NULL COMMENT '链接名称',
    `description` VARCHAR(300) DEFAULT NULL COMMENT '描述',
    `url` VARCHAR(500) NOT NULL COMMENT '跳转地址',
    `icon` VARCHAR(100) DEFAULT NULL COMMENT '图标名称',
    `sort` INT NOT NULL DEFAULT 0 COMMENT '排序号（升序）',
    `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用（1=是, 0=否）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='首页常用链接配置表';

-- =============================================
-- 4. 最近访问记录表
-- =============================================
DROP TABLE IF EXISTS `sys_recent_visit`;
CREATE TABLE `sys_recent_visit` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id` BIGINT NOT NULL COMMENT '用户 ID',
    `page_path` VARCHAR(200) NOT NULL COMMENT '页面路由路径',
    `page_title` VARCHAR(100) NOT NULL COMMENT '页面标题',
    `visited_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '访问时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_visited` (`user_id`, `visited_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户最近访问记录表';

-- =============================================
-- 5. 用户表（基础版）
-- =============================================
DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `username` VARCHAR(64) NOT NULL COMMENT '用户名',
    `password_hash` VARCHAR(256) NOT NULL COMMENT '密码哈希',
    `email` VARCHAR(128) DEFAULT NULL COMMENT '邮箱',
    `role` VARCHAR(32) NOT NULL DEFAULT 'user' COMMENT '角色',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username_deleted` (`username`, `deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- =============================================
-- 初始化数据
-- =============================================

-- 常用链接初始数据
INSERT INTO `sys_common_link` (`title`, `description`, `url`, `icon`, `sort`, `enabled`) VALUES
('CMDB 虚拟机列表', '管理所有虚拟机资产', '/cmdb', 'Document', 1, 1),
('性能监控大盘', '实时查看系统性能指标', '/monitor', 'TrendCharts', 2, 1),
('系统配置', '修改系统参数和设置', '/settings', 'Setting', 3, 1),
('帮助文档', '查看使用指南和文档', '/doc', 'Link', 4, 1);

-- 系统状态初始快照
INSERT INTO `sys_monitor` (`server_online`, `service_running`, `network_status`, `storage_usage`, `alert_pending`, `cpu_load`) VALUES
(24, 142, 'normal', '78%', 3, '45%');

-- CMDB 虚拟机初始数据
INSERT INTO `cmdb_vm` (`name`, `cluster`, `external_ip`, `internal_ip`, `description`, `status`, `tenant`, `vcpus`, `memory`, `disk`, `access_url`, `created_by`) VALUES
('vm-web-01', 'OpenClaw-Main', '38.246.245.32', '10.0.118.4', 'OpenClaw 主节点 - 文档归档/Git 推送', 1, 'OpenClaw', 4, 8192, '100GB', 'portal.mubai.top', 'admin'),
('k8s-master-01', 'K8s-Production', '192.168.1.100', '10.0.119.5', 'K8s 生产集群 - master 节点', 1, 'OpenClaw', 8, 16384, '200GB', 'k8s.example.com', 'admin'),
('infra-node-01', 'Infra-Cluster', '10.0.1.50', '10.0.1.51', '基础设施集群 - 监控/日志', 0, 'OpenClaw', 2, 4096, '50GB', '', 'admin'),
('vm-compute-01', 'OpenClaw-Main', '38.246.245.33', '10.0.118.5', 'OpenClaw 从节点 - 计算任务', 1, 'OpenClaw', 16, 32768, '500GB', '', 'admin'),
('dev-test-01', 'Dev-Cluster', '10.10.1.20', '172.16.1.20', '开发测试环境', 1, 'Platform', 4, 8192, '100GB', 'dev.mubai.top', 'admin'),
('k8s-worker-01', 'K8s-Production', '192.168.1.101', '10.0.119.6', 'K8s 生产集群 - worker 节点', 1, 'OpenClaw', 8, 16384, '500GB', '', 'admin'),
('prometheus-01', 'Infra-Cluster', '10.0.1.52', '10.0.1.53', 'Prometheus 监控节点', 1, 'Monitoring', 4, 8192, '200GB', 'prometheus.mubai.top', 'admin'),
('grafana-01', 'Infra-Cluster', '10.0.1.54', '10.0.1.55', 'Grafana 面板节点', 1, 'Monitoring', 2, 4096, '50GB', 'grafana.mubai.top', 'admin'),
('jenkins-01', 'Dev-Cluster', '10.10.1.21', '172.16.1.21', 'CI/CD Jenkins 节点', 1, 'Platform', 4, 8192, '100GB', 'jenkins.mubai.top', 'admin'),
('api-gateway-01', 'OpenClaw-Main', '38.246.245.34', '10.0.118.6', 'API 网关节点', 1, 'OpenClaw', 4, 8192, '100GB', 'api.mubai.top', 'admin'),
('k8s-worker-02', 'K8s-Production', '192.168.1.102', '10.0.119.7', 'K8s 生产集群 - worker 节点', 0, 'OpenClaw', 8, 16384, '500GB', '', 'admin'),
('gitlab-01', 'Dev-Cluster', '10.10.1.22', '172.16.1.22', 'GitLab 代码仓库', 1, 'Platform', 4, 8192, '500GB', 'gitlab.mubai.top', 'admin');
