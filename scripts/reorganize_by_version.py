#!/usr/bin/env python3
"""
按版本号重新组织需求：
- 创建版本项目（1.0.1 ~ 1.1.0）
- 将现有需求按版本归类
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.requirement import Project, Requirement

# 版本项目定义
VERSIONS = {
    "1.0.1": "CMDB 与待办管理",
    "1.0.2": "数据库管理与 AI 辅助",
    "1.0.3": "部署配置统一 & 侧边栏优化",
    "1.0.4": "导航栏优化 & 版本管理",
    "1.0.5": "API 路径修复 & 用户信息迁移",
    "1.0.6": "监控面板 AI 管理模块",
    "1.0.7": "指标告警 + 运维中心 + 系统管理",
    "1.0.8": "代码库管理功能",
    "1.0.9": "Jenkins 集成 + 服务备份 + 需求升级",
    "1.1.0": "小程序 & 移动端适配",
}

# 需求标题关键词 → 版本号映射
REQUIREMENT_VERSION_MAP = {
    # 1.0.1 - CMDB 与待办管理
    "CMDB": "1.0.1", "虚拟机管理": "1.0.1", "待办": "1.0.1", "初始": "1.0.1", "项目初始化": "1.0.1",
    # 1.0.2 - 数据库管理与 AI 辅助
    "数据库": "1.0.2", "SQL": "1.0.2", "DashScope": "1.0.2",
    # 1.0.3 - 部署配置统一
    "部署配置": "1.0.3", "Docker": "1.0.3", "nginx": "1.0.3", "侧边栏": "1.0.3",
    # 1.0.4 - 导航栏优化 & 版本管理
    "版本记录": "1.0.4", "导航栏": "1.0.4", "Logo": "1.0.4",
    # 1.0.5 - API 路径修复 & 用户信息迁移
    "API 路径": "1.0.5", "用户信息": "1.0.5", "登录": "1.0.5", "proxy": "1.0.5",
    # 1.0.6 - 监控面板 AI 管理
    "监控面板": "1.0.6", "Grafana 面板": "1.0.6", "AI 面板": "1.0.6", "Grafana API Key": "1.0.6",
    # 1.0.7 - 指标告警 + 运维中心 + 系统管理
    "告警": "1.0.7", "指标": "1.0.7", "运维中心": "1.0.7", "系统管理": "1.0.7",
    "用户管理": "1.0.7", "角色管理": "1.0.7", "菜单管理": "1.0.7", "部门管理": "1.0.7",
    "审批": "1.0.7", "配置管理": "1.0.7", "密码": "1.0.7", "证书": "1.0.7",
    "AI层": "1.0.7", "性能测试": "1.0.7",
    # 1.0.8 - 代码库管理
    "代码库": "1.0.8", "仓库": "1.0.8", "Git": "1.0.8", "GitHub": "1.0.8",
    # 1.0.9 - Jenkins + 服务备份 + 需求升级
    "Jenkins": "1.0.9", "流水线": "1.0.9", "备份": "1.0.9", "服务备份": "1.0.9",
    "需求管理": "1.0.9", "待办升级": "1.0.9", "容器化": "1.0.9", "node纳管": "1.0.9",
    "自动化部署": "1.0.9", "portal工具": "1.0.9", "新功能": "1.0.9", "其他功能": "1.0.9",
    # 1.1.0 - 未来版本
    "小程序": "1.1.0", "手机": "1.1.0", "移动端": "1.1.0",
}


def classify_requirement(title):
    """根据标题关键词分类到版本（不区分大小写）"""
    title_lower = title.lower()
    for keyword, version in REQUIREMENT_VERSION_MAP.items():
        if keyword.lower() in title_lower:
            return version
    return None


def main():
    app = create_app()
    with app.app_context():
        # 1. 创建版本项目
        version_projects = {}
        for version, name in VERSIONS.items():
            project_name = f"{version} 版本"
            existing = Project.query.filter_by(name=project_name).first()
            if existing:
                version_projects[version] = existing
                print(f"♻️  复用项目: {project_name} (id={existing.id})")
            else:
                project = Project(name=project_name, description=name, status="active")
                db.session.add(project)
                db.session.flush()
                version_projects[version] = project
                print(f"✨ 创建项目: {project_name} (id={project.id})")

        db.session.commit()

        # 2. 获取所有需求（排除已归类到版本项目的）
        all_reqs = Requirement.query.filter(Requirement.deleted_at.is_(None)).all()

        # 3. 重新归类需求
        moved_count = 0
        unmapped = []
        for req in all_reqs:
            version = classify_requirement(req.title)
            if version and version in version_projects:
                new_project = version_projects[version]
                if req.project_id != new_project.id:
                    old_project = Project.query.get(req.project_id)
                    old_name = old_project.name if old_project else "?"
                    req.project_id = new_project.id
                    moved_count += 1
                    print(f"   [{version}] {req.title} ({old_name} → {new_project.name})")
            else:
                unmapped.append(req)

        db.session.commit()

        print(f"\n✅ 完成! 移动了 {moved_count} 个需求到版本项目")
        if unmapped:
            print(f"\n⚠️  以下 {len(unmapped)} 个需求未匹配到版本:")
            for req in unmapped:
                print(f"  - {req.title} (id={req.id})")


if __name__ == "__main__":
    main()
