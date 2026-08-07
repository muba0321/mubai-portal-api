"""
运维作业相关模型
"""
from datetime import datetime
from app.extensions import db


class AnsibleJob(db.Model):
    """作业记录"""
    __tablename__ = "ansible_job"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    job_name = db.Column(db.String(200), comment="作业名称")
    job_type = db.Column(db.String(20), default="ad_hoc", comment="类型: ad_hoc/playbook/script")
    module = db.Column(db.String(100), default="shell", comment="模块: shell/command/raw")
    module_args = db.Column(db.Text, comment="命令内容")
    targets = db.Column(db.Text, comment="目标主机 IP 列表 (JSON)")
    extra_vars = db.Column(db.Text, comment="额外变量 (JSON)")
    status = db.Column(db.String(20), default="pending", comment="pending/running/success/failed/timeout")
    created_by = db.Column(db.String(64), comment="创建人")
    started_at = db.Column(db.DateTime, comment="开始时间")
    finished_at = db.Column(db.DateTime, comment="结束时间")
    duration = db.Column(db.Integer, comment="执行耗时(秒)")
    result = db.Column(db.Text, comment="执行结果 (JSON)")
    error_msg = db.Column(db.Text, comment="错误信息")
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<AnsibleJob {self.id} {self.job_name}>"


class AnsibleSchedule(db.Model):
    """定时任务"""
    __tablename__ = "ansible_schedule"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), comment="任务名称")
    job_id = db.Column(db.BigInteger, db.ForeignKey("ansible_job.id"), comment="关联作业模板 ID")
    task_type = db.Column(db.String(30), default="command", comment="任务类型: command/cmdb_update/disk_check/service_check/backup")
    command = db.Column(db.Text, comment="执行命令 (task_type=command 时使用)")
    cron_expression = db.Column(db.String(100), comment="Cron 表达式")
    enabled = db.Column(db.Boolean, default=True, comment="是否启用")
    last_run = db.Column(db.DateTime, comment="上次执行时间")
    next_run = db.Column(db.DateTime, comment="下次执行时间")
    last_status = db.Column(db.String(20), comment="上次执行状态: success/failed/error")
    created_by = db.Column(db.String(64), comment="创建人")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationship
    job = db.relationship("AnsibleJob", backref="schedules")

    def __repr__(self):
        return f"<AnsibleSchedule {self.id} {self.name}>"


class AnsibleScheduleLog(db.Model):
    """定时任务执行历史"""
    __tablename__ = "ansible_schedule_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.BigInteger, db.ForeignKey("ansible_schedule.id"), comment="关联定时任务 ID")
    schedule_name = db.Column(db.String(200), comment="任务名称")
    task_type = db.Column(db.String(30), comment="任务类型")
    status = db.Column(db.String(20), comment="success/failed/error")
    output = db.Column(db.Text, comment="执行输出")
    error_msg = db.Column(db.Text, comment="错误信息")
    duration = db.Column(db.Integer, comment="执行耗时(秒)")
    started_at = db.Column(db.DateTime, comment="开始时间")

    def __repr__(self):
        return f"<AnsibleScheduleLog {self.id} {self.status}>"


class AnsibleCommand(db.Model):
    """快捷命令模板"""
    __tablename__ = "ansible_command"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment="命令名称")
    category = db.Column(db.String(50), default="custom", comment="分类: system/service/docker/network/disk/custom")
    command = db.Column(db.Text, nullable=False, comment="命令内容，支持变量 {host} {date} {days} 等")
    description = db.Column(db.String(500), comment="命令说明")
    module = db.Column(db.String(50), default="shell", comment="默认模块")
    sort = db.Column(db.Integer, default=0, comment="排序")
    enabled = db.Column(db.Boolean, default=True, comment="是否启用")

    def __repr__(self):
        return f"<AnsibleCommand {self.name}>"
