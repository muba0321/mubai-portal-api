from app.views.auth import auth_bp
from app.views.cmdb import cmdb_bp
from app.views.dashboard import dashboard_bp
from app.views.database import database_bp
from app.views.monitoring import monitoring_bp
from app.views.setting import config_bp
from app.views.system import system_bp
from app.views.todo import todo_bp
from app.views.todo_extend import todo_extend_bp
from app.views.grafana import grafana_bp
from app.views.alerting import alerting_bp
from app.views.ansible import ansible_bp
# RBAC views
from app.views.sys_user import sys_user_bp
from app.views.sys_dept import sys_dept_bp
from app.views.sys_role import sys_role_bp
from app.views.sys_menu import sys_menu_bp
from app.views.sys_log import sys_log_bp
from app.views.approval import approval_bp
# 配置源管理
from app.views.config_source import config_source_bp
# 密码管理
from app.views.credential import credential_bp
# Git 仓库管理
from app.views.git_repo import git_bp
# 服务备份管理
from app.views.backup import backup_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(cmdb_bp, url_prefix="/api/v1/cmdb")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(database_bp, url_prefix="/api/v1/database")
    app.register_blueprint(monitoring_bp, url_prefix="/api/v1/monitoring")
    app.register_blueprint(grafana_bp, url_prefix="/api/v1/grafana")
    app.register_blueprint(config_bp, url_prefix="/api/v1/configs")
    app.register_blueprint(system_bp, url_prefix="/api/v1")
    app.register_blueprint(todo_bp, url_prefix="/api/v1/todo")
    app.register_blueprint(todo_extend_bp, url_prefix="/api/v1/todo")
    app.register_blueprint(alerting_bp, url_prefix="/api/v1/alerting")
    app.register_blueprint(ansible_bp, url_prefix="/api/v1/ansible")
    # RBAC
    app.register_blueprint(sys_user_bp, url_prefix="/api/v1/users")
    app.register_blueprint(sys_dept_bp, url_prefix="/api/v1/depts")
    app.register_blueprint(sys_role_bp, url_prefix="/api/v1/roles")
    app.register_blueprint(sys_menu_bp, url_prefix="/api/v1/menus")
    app.register_blueprint(sys_log_bp, url_prefix="/api/v1/logs")
    # 审批流
    app.register_blueprint(approval_bp, url_prefix="/api/v1/approvals")
    # 配置源管理
    app.register_blueprint(config_source_bp)
    # 密码管理
    app.register_blueprint(credential_bp, url_prefix="/api/v1")
    # Git 仓库管理
    app.register_blueprint(git_bp, url_prefix="/api/v1/git")

    # Jenkins 管理
    from app.views.jenkins import jenkins_bp
    app.register_blueprint(jenkins_bp, url_prefix="/api/v1/jenkins")

    # 服务备份管理
    from app.views.backup import backup_bp
    app.register_blueprint(backup_bp, url_prefix="/api/v1/backup")
