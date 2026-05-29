"""RBAC 种子数据初始化"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.dept import Dept
from app.models.sys_user import SysUser
from app.models.sys_role import Role
from app.models.sys_user_role import UserRole
from app.models.sys_menu import Menu
from app.models.sys_role_menu import RoleMenu
from werkzeug.security import generate_password_hash


def seed_data():
    # ========== 1. 部门 ==========
    depts = [
        {"id": 1, "name": "公司", "parent_id": 0, "ancestors": "0", "sort": 0},
        {"id": 2, "name": "运维部", "parent_id": 1, "ancestors": "0,1", "sort": 1},
        {"id": 3, "name": "开发部", "parent_id": 1, "ancestors": "0,1", "sort": 2},
        {"id": 4, "name": "测试部", "parent_id": 1, "ancestors": "0,1", "sort": 3},
        {"id": 5, "name": "SRE 一组", "parent_id": 2, "ancestors": "0,1,2", "sort": 1},
        {"id": 6, "name": "SRE 二组", "parent_id": 2, "ancestors": "0,1,2", "sort": 2},
    ]
    for d in depts:
        if not Dept.query.get(d["id"]):
            db.session.add(Dept(**d))

    # ========== 2. 角色 ==========
    roles = [
        {"id": 1, "name": "超级管理员", "code": "super_admin", "sort": 1, "data_scope": "all", "remark": "系统超级管理员，拥有全部权限"},
        {"id": 2, "name": "部门负责人", "code": "dept_manager", "sort": 2, "data_scope": "dept_and_child", "remark": "负责本部门及下级部门的管理"},
        {"id": 3, "name": "部门成员", "code": "dept_member", "sort": 3, "data_scope": "dept", "remark": "仅能查看本部门数据"},
        {"id": 4, "name": "只读访客", "code": "viewer", "sort": 4, "data_scope": "self", "remark": "仅能查看本人数据"},
    ]
    for r in roles:
        if not Role.query.get(r["id"]):
            db.session.add(Role(**r))

    # ========== 3. 菜单 ==========
    menus = [
        # 系统管理 (目录)
        {"id": 1, "parent_id": 0, "name": "系统管理", "code": "", "type": "C", "path": "/system", "icon": "Setting", "sort": 10, "visible": 1, "status": 1},
        # 用户管理 (菜单)
        {"id": 2, "parent_id": 1, "name": "用户管理", "code": "", "type": "M", "path": "users", "icon": "UserFilled", "sort": 1, "visible": 1, "status": 1, "component": "system/users/index"},
        {"id": 3, "parent_id": 2, "name": "用户查询", "code": "sys:user:list", "type": "B", "sort": 1, "visible": 1, "status": 1},
        {"id": 4, "parent_id": 2, "name": "用户新增", "code": "sys:user:create", "type": "B", "sort": 2, "visible": 1, "status": 1},
        {"id": 5, "parent_id": 2, "name": "用户修改", "code": "sys:user:update", "type": "B", "sort": 3, "visible": 1, "status": 1},
        {"id": 6, "parent_id": 2, "name": "用户删除", "code": "sys:user:delete", "type": "B", "sort": 4, "visible": 1, "status": 1},
        {"id": 7, "parent_id": 2, "name": "重置密码", "code": "sys:user:reset-password", "type": "B", "sort": 5, "visible": 1, "status": 1},
        {"id": 8, "parent_id": 2, "name": "导入", "code": "sys:user:import", "type": "B", "sort": 6, "visible": 1, "status": 1},
        {"id": 9, "parent_id": 2, "name": "导出", "code": "sys:user:export", "type": "B", "sort": 7, "visible": 1, "status": 1},
        # 角色管理 (菜单)
        {"id": 10, "parent_id": 1, "name": "角色管理", "code": "", "type": "M", "path": "role", "icon": "Avatar", "sort": 2, "visible": 1, "status": 1, "component": "system/role/index"},
        {"id": 11, "parent_id": 10, "name": "角色查询", "code": "sys:role:list", "type": "B", "sort": 1, "visible": 1, "status": 1},
        {"id": 12, "parent_id": 10, "name": "角色新增", "code": "sys:role:create", "type": "B", "sort": 2, "visible": 1, "status": 1},
        {"id": 13, "parent_id": 10, "name": "角色修改", "code": "sys:role:update", "type": "B", "sort": 3, "visible": 1, "status": 1},
        {"id": 14, "parent_id": 10, "name": "角色删除", "code": "sys:role:delete", "type": "B", "sort": 4, "visible": 1, "status": 1},
        {"id": 15, "parent_id": 10, "name": "分配权限", "code": "sys:role:assign", "type": "B", "sort": 5, "visible": 1, "status": 1},
        # 菜单管理 (菜单)
        {"id": 16, "parent_id": 1, "name": "菜单管理", "code": "", "type": "M", "path": "menu", "icon": "Menu", "sort": 3, "visible": 1, "status": 1, "component": "system/menu/index"},
        {"id": 17, "parent_id": 16, "name": "菜单查询", "code": "sys:menu:list", "type": "B", "sort": 1, "visible": 1, "status": 1},
        {"id": 18, "parent_id": 16, "name": "菜单新增", "code": "sys:menu:create", "type": "B", "sort": 2, "visible": 1, "status": 1},
        {"id": 19, "parent_id": 16, "name": "菜单修改", "code": "sys:menu:update", "type": "B", "sort": 3, "visible": 1, "status": 1},
        {"id": 20, "parent_id": 16, "name": "菜单删除", "code": "sys:menu:delete", "type": "B", "sort": 4, "visible": 1, "status": 1},
        # 部门管理 (菜单)
        {"id": 21, "parent_id": 1, "name": "部门管理", "code": "", "type": "M", "path": "dept", "icon": "OfficeBuilding", "sort": 4, "visible": 1, "status": 1, "component": "system/dept/index"},
        {"id": 22, "parent_id": 21, "name": "部门查询", "code": "sys:dept:list", "type": "B", "sort": 1, "visible": 1, "status": 1},
        {"id": 23, "parent_id": 21, "name": "部门新增", "code": "sys:dept:create", "type": "B", "sort": 2, "visible": 1, "status": 1},
        {"id": 24, "parent_id": 21, "name": "部门修改", "code": "sys:dept:update", "type": "B", "sort": 3, "visible": 1, "status": 1},
        {"id": 25, "parent_id": 21, "name": "部门删除", "code": "sys:dept:delete", "type": "B", "sort": 4, "visible": 1, "status": 1},
        # 操作日志 (菜单)
        {"id": 26, "parent_id": 1, "name": "操作日志", "code": "", "type": "M", "path": "log", "icon": "Document", "sort": 5, "visible": 1, "status": 1, "component": "system/log/index"},
        {"id": 27, "parent_id": 26, "name": "日志查询", "code": "sys:log:list", "type": "B", "sort": 1, "visible": 1, "status": 1},
        # 其他顶级菜单
        {"id": 30, "parent_id": 0, "name": "首页", "code": "", "type": "C", "path": "/dashboard", "icon": "HomeFilled", "sort": 1, "visible": 1, "status": 1},
        {"id": 31, "parent_id": 30, "name": "首页", "code": "", "type": "M", "path": "index", "icon": "HomeFilled", "sort": 1, "visible": 1, "status": 1, "component": "dashboard/index"},
        {"id": 40, "parent_id": 0, "name": "监控中心", "code": "", "type": "C", "path": "/monitoring", "icon": "Monitor", "sort": 2, "visible": 1, "status": 1},
        {"id": 41, "parent_id": 40, "name": "监控大屏", "code": "", "type": "M", "path": "index", "icon": "Odometer", "sort": 1, "visible": 1, "status": 1, "component": "monitoring/index"},
        {"id": 42, "parent_id": 40, "name": "面板管理", "code": "", "type": "M", "path": "grafana", "icon": "DataBoard", "sort": 2, "visible": 1, "status": 1, "component": "grafana/index"},
        {"id": 50, "parent_id": 0, "name": "告警管理", "code": "", "type": "C", "path": "/alerting", "icon": "Bell", "sort": 3, "visible": 1, "status": 1},
        {"id": 51, "parent_id": 50, "name": "指标与告警", "code": "", "type": "M", "path": "index", "icon": "Bell", "sort": 1, "visible": 1, "status": 1, "component": "alerting/index"},
        {"id": 60, "parent_id": 0, "name": "运维中心", "code": "", "type": "C", "path": "/ops", "icon": "Connection", "sort": 4, "visible": 1, "status": 1},
        {"id": 61, "parent_id": 60, "name": "作业执行", "code": "", "type": "M", "path": "executor", "icon": "Pointer", "sort": 1, "visible": 1, "status": 1, "component": "ops/Executor"},
        {"id": 62, "parent_id": 60, "name": "作业历史", "code": "", "type": "M", "path": "history", "icon": "Document", "sort": 2, "visible": 1, "status": 1, "component": "ops/History"},
        {"id": 63, "parent_id": 60, "name": "定时任务", "code": "", "type": "M", "path": "schedules", "icon": "Clock", "sort": 3, "visible": 1, "status": 1, "component": "ops/Schedules"},
        {"id": 64, "parent_id": 60, "name": "主机清单", "code": "", "type": "M", "path": "inventory", "icon": "Grid", "sort": 4, "visible": 1, "status": 1, "component": "ops/Inventory"},
        {"id": 70, "parent_id": 0, "name": "数据库管理", "code": "", "type": "C", "path": "/database", "icon": "DataBoard", "sort": 5, "visible": 1, "status": 1},
        {"id": 71, "parent_id": 70, "name": "数据库管理", "code": "", "type": "M", "path": "index", "icon": "DataBoard", "sort": 1, "visible": 1, "status": 1, "component": "database/index"},
        {"id": 80, "parent_id": 0, "name": "CMDB", "code": "", "type": "C", "path": "/cmdb", "icon": "Monitor", "sort": 6, "visible": 1, "status": 1},
        {"id": 81, "parent_id": 80, "name": "虚拟机管理", "code": "", "type": "M", "path": "index", "icon": "Monitor", "sort": 1, "visible": 1, "status": 1, "component": "cmdb/index"},
        {"id": 90, "parent_id": 0, "name": "待办管理", "code": "", "type": "C", "path": "/todo", "icon": "List", "sort": 7, "visible": 1, "status": 1},
        {"id": 91, "parent_id": 90, "name": "待办管理", "code": "", "type": "M", "path": "index", "icon": "List", "sort": 1, "visible": 1, "status": 1, "component": "todo/index"},
        {"id": 100, "parent_id": 0, "name": "版本记录", "code": "", "type": "C", "path": "/changelog", "icon": "Stamp", "sort": 8, "visible": 1, "status": 1},
        {"id": 101, "parent_id": 100, "name": "版本记录", "code": "", "type": "M", "path": "index", "icon": "Stamp", "sort": 1, "visible": 1, "status": 1, "component": "changelog/index"},
    ]
    for m in menus:
        if not Menu.query.get(m["id"]):
            db.session.add(Menu(**m))

    # ========== 4. 迁移/创建管理员用户 ==========
    # 将现有 User 表的 admin 用户迁移到 SysUser，如果不存在则创建
    try:
        from app.models.user import User
        existing_admin = User.query.filter_by(username="admin").first()
    except (ImportError, ModuleNotFoundError):
        existing_admin = None
    if not SysUser.query.filter_by(username="admin").first():
        admin = SysUser(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            nickname="管理员",
            dept_id=1,
            identity="admin",
            is_admin=1,
        )
        db.session.add(admin)
        db.session.flush()
        admin_id = admin.id
        print(f"创建管理员用户 (id={admin_id}, 密码: admin123)")
    else:
        admin = SysUser.query.filter_by(username="admin").first()
        admin_id = admin.id

    # 迁移现有 User 表中的其他用户
    for old_user in User.query.all():
        if old_user.username == "admin":
            continue
        if not SysUser.query.filter_by(username=old_user.username).first():
            new_user = SysUser(
                username=old_user.username,
                password_hash=old_user.password_hash,
                email=old_user.email,
                identity="admin" if old_user.role == "admin" else "member",
                is_admin=1 if old_user.role == "admin" else 0,
            )
            db.session.add(new_user)
            db.session.flush()

    # ========== 5. 绑定 super_admin 角色 ==========
    if not UserRole.query.filter_by(user_id=admin_id, role_id=1).first():
        db.session.add(UserRole(user_id=admin_id, role_id=1))

    # ========== 6. super_admin 绑定全部菜单 ==========
    all_menu_ids = [m["id"] for m in menus]
    for mid in all_menu_ids:
        if not RoleMenu.query.filter_by(role_id=1, menu_id=mid).first():
            db.session.add(RoleMenu(role_id=1, menu_id=mid))

    db.session.commit()
    print("RBAC 种子数据初始化完成")


app = create_app("production")
with app.app_context():
    seed_data()
