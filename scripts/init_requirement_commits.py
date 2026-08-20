#!/usr/bin/env python3
"""
从 Git 历史提交中智能归类生成需求，并建立需求↔提交的多对多关联。

用法：python scripts/init_requirement_commits.py
"""
import sys
import os
import json
import subprocess
from datetime import datetime, date

# 确保能导入 app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.requirement import Project, Requirement, RequirementCommit

# ============ 配置 ============

REPOS = {
    "后端": "/opt/repos/backend",
    "前端": "/opt/repos/frontend",
}

# 默认项目 ID（portal工具开发）
DEFAULT_PROJECT_ID = 3

# 提交归类规则：关键词 → 需求标题
# 按优先级匹配，先匹配的归类到同一需求
KEYWORD_RULES = [
    # Jenkins / CI-CD
    (["jenkins", "Jenkinsfile", "CI/CD", "流水线", "deploy", "部署", "docker compose", "Dockerfile", "构建"],
     "Jenkins 流水线管理集成"),
    # 需求管理（从待办升级）
    (["待办", "需求", "requirement", "todo", "TodoItem", "看板", "日历", "统计"],
     "待办升级为需求管理模块"),
    # Git 仓库管理
    (["Git", "仓库", "github", "commit", "branch", "tag", "diff", "blame"],
     "代码库管理功能"),
    # 服务备份
    (["备份", "backup", "服务管理", "ServiceBackup"],
     "服务备份管理"),
    # 运维中心
    (["运维", "SSH", "ansible", "主机清单", "作业", "定时任务", "Schedules", "Inventory", "Executor"],
     "运维中心改造"),
    # 监控告警
    (["监控", "告警", "alert", "Prometheus", "Grafana", "面板", "dashboard", "monitor"],
     "监控中心 + 告警管理"),
    # 密码/凭据管理
    (["密码", "credential", "凭据"],
     "密码管理功能"),
    # 数据库
    (["数据库", "SQL", "mysql", "NL-to-SQL", "DashScope"],
     "数据库管理 + AI SQL 生成"),
    # 版本记录
    (["版本", "changelog", "VERSION"],
     "版本记录页面"),
    # 系统管理
    (["系统管理", "用户", "角色", "菜单", "部门", "配置", "Apollo", "RBAC"],
     "系统管理模块完善"),
    # 前端基础
    (["nginx", "proxy", "Docker", "docker", "vite", "Dockerfile", "端口", "upstream", "favicon"],
     "前端基础架构与部署配置"),
    # 初始版本
    (["init", "初始", "scaffold", "v1.0.0"],
     "SRE Portal 项目初始化"),
    # CMDB
    (["CMDB", "虚拟机", "cmdb_vm"],
     "CMDB 虚拟机管理"),
]

# 默认需求标题（未匹配到任何规则）
DEFAULT_TITLE = "其他功能改进"


def get_commits(repo_path, since="2026-04-01", until="2026-09-01"):
    """获取指定时间范围的提交记录"""
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H|%s|%an|%ai", f"--since={since}", f"--until={until}"],
            capture_output=True, text=True, cwd=repo_path, timeout=15
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) < 4:
                continue
            commits.append({
                "hash": parts[0],
                "subject": parts[1],
                "author": parts[2],
                "date": parts[3].split(" ")[0],
            })
        return commits
    except Exception as e:
        print(f"  [错误] 获取提交失败: {e}")
        return []


def get_commit_files(repo_path, commit_hash):
    """获取提交的文件变更"""
    try:
        result = subprocess.run(
            ["git", "show", "--format=", "--numstat", commit_hash],
            capture_output=True, text=True, cwd=repo_path, timeout=5
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split("\t")
            if len(parts) == 3 and parts[2].endswith((".py", ".ts", ".vue", ".js", ".sql", ".yml", ".yaml", ".json")):
                files.append({
                    "path": parts[2],
                    "additions": int(parts[0]) if parts[0] != "-" else 0,
                    "deletions": int(parts[1]) if parts[1] != "-" else 0,
                })
        return files
    except:
        return []


def classify_commit(subject):
    """根据提交主题分类到需求"""
    for keywords, title in KEYWORD_RULES:
        for kw in keywords:
            if kw.lower() in subject.lower():
                return title
    return DEFAULT_TITLE


def main():
    app = create_app()
    with app.app_context():
        # 确保项目存在
        project = Project.query.get(DEFAULT_PROJECT_ID)
        if not project:
            project = Project(id=DEFAULT_PROJECT_ID, name="portal工具开发", status="active")
            db.session.add(project)
            db.session.commit()

        total_commits = 0
        total_requirements = 0
        total_links = 0

        # 收集所有提交，按归类分组
        requirement_commits_map = {}  # title -> [(module, commit, files)]

        for module, repo_path in REPOS.items():
            print(f"\n📦 扫描 {module} 仓库: {repo_path}")
            if not os.path.exists(os.path.join(repo_path, ".git")):
                print(f"  ⚠️ 仓库不存在，跳过")
                continue

            commits = get_commits(repo_path)
            print(f"  找到 {len(commits)} 个提交")

            for commit in commits:
                title = classify_commit(commit["subject"])
                if title not in requirement_commits_map:
                    requirement_commits_map[title] = []

                files = get_commit_files(repo_path, commit["hash"])
                requirement_commits_map[title].append((module, commit, files))
                total_commits += 1

        # 为每个归类创建需求并关联提交
        for title, commit_list in requirement_commits_map.items():
            # 按日期范围确定需求的起止日期
            dates = sorted(set(c["date"] for _, c, _ in commit_list))
            start_date = dates[0] if dates else None
            end_date = dates[-1] if dates else None

            # 确定状态
            statuses = [c["subject"] for _, c, _ in commit_list]
            is_fix_only = all(s.lower().startswith("fix:") or s.lower().startswith("chore:") for s in statuses)
            status = "done" if is_fix_only else "done"

            # 检查需求是否已存在
            existing = Requirement.query.filter_by(title=title, project_id=DEFAULT_PROJECT_ID).first()
            if existing:
                req = existing
                print(f"  ♻️  复用已有需求: {title} (id={req.id})")
            else:
                req = Requirement(
                    project_id=DEFAULT_PROJECT_ID,
                    title=title,
                    description=f"自动从 Git 提交历史归类生成。涵盖 {len(commit_list)} 个提交，日期 {start_date} ~ {end_date}",
                    requirement_type="feature",
                    priority="P2",
                    status=status,
                    due_date=datetime.strptime(end_date, "%Y-%m-%d") if end_date else None,
                    completed_at=datetime.strptime(end_date, "%Y-%m-%d") if end_date else None,
                )
                db.session.add(req)
                db.session.flush()
                total_requirements += 1
                print(f"  ✨ 创建需求: {title} (id={req.id}, {len(commit_list)} 个提交)")

            # 关联提交
            for module, commit, files in commit_list:
                # 检查是否已关联
                existing_link = RequirementCommit.query.filter_by(
                    requirement_id=req.id,
                    repo_module=module,
                    commit_hash=commit["hash"],
                ).first()
                if existing_link:
                    continue

                link = RequirementCommit(
                    requirement_id=req.id,
                    repo_module=module,
                    commit_hash=commit["hash"],
                    commit_subject=commit["subject"],
                    commit_date=datetime.strptime(commit["date"], "%Y-%m-%d").date() if commit["date"] else None,
                    commit_author=commit["author"],
                    files_changed=files,
                )
                db.session.add(link)
                total_links += 1

        db.session.commit()
        print(f"\n✅ 完成! 需求: {total_requirements} 新增, 提交关联: {total_links}, 总提交: {total_commits}")


if __name__ == "__main__":
    main()
