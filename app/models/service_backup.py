"""
服务备份管理模型
"""
from datetime import datetime
from app.extensions import db


class ServiceBackup(db.Model):
    """服务管理配置（含备份 + 进程状态）"""
    __tablename__ = "service_backup"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment="服务名称")
    category = db.Column(db.String(30), comment="分类: database/monitoring/cicd/config/gateway/application/documentation")
    description = db.Column(db.Text, comment="功能描述")
    server_ip = db.Column(db.String(20), comment="所属服务器 IP")
    server_name = db.Column(db.String(100), comment="所属服务器名称")
    port = db.Column(db.Integer, comment="服务端口")

    # 进程/容器信息
    process_type = db.Column(db.String(30), comment="进程类型: docker/systemd/native")
    process_name = db.Column(db.String(100), comment="进程/容器名称")
    check_command = db.Column(db.Text, comment="状态检测命令")

    # 备份相关
    backup_method = db.Column(db.String(50), comment="备份方式: mysqldump/tar/rsync/docker-export/docker-cp/systemd-unit/skip")
    backup_path = db.Column(db.String(500), comment="备份文件存储路径")
    backup_script = db.Column(db.Text, comment="备份脚本/命令")
    restore_steps = db.Column(db.Text, comment="恢复步骤（JSON 数组）")
    enabled = db.Column(db.Boolean, default=True, comment="是否启用备份")
    sort = db.Column(db.Integer, default=0, comment="排序")
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 关系
    logs = db.relationship("ServiceBackupLog", backref="service", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ServiceBackup {self.name}>"


class ServiceBackupLog(db.Model):
    """服务备份执行日志"""
    __tablename__ = "service_backup_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service_backup.id"), comment="关联服务 ID")
    status = db.Column(db.String(20), comment="success/failed/skipped")
    file_name = db.Column(db.String(255), comment="备份文件名")
    file_path = db.Column(db.String(500), comment="备份文件路径")
    file_size = db.Column(db.BigInteger, comment="文件大小(bytes)")
    file_md5 = db.Column(db.String(64), comment="文件 MD5 校验值")
    error_msg = db.Column(db.Text, comment="错误信息")
    duration = db.Column(db.Integer, comment="执行耗时(秒)")
    started_at = db.Column(db.DateTime, comment="开始时间")

    def __repr__(self):
        return f"<ServiceBackupLog {self.id} {self.status}>"
