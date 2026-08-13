"""
Git 仓库管理 API - 使用 GitHub API（公开仓库无需认证）
提供仓库概览、提交历史、分支/Tag、文件浏览、Diff 等功能
"""
import os
import requests
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.utils.response import success, error

logger = logging.getLogger("sre-portal")

git_bp = Blueprint("git", __name__)

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # GitHub Token 用于提高 API 限流

# 缓存：{url: (timestamp, data)}
_github_cache = {}
CACHE_TTL = 300  # 5 分钟缓存

REPOS = {
    "frontend": {
        "owner": "muba0321",
        "repo": "mubai-portal",
        "name": "mubai-portal",
        "description": "SRE Portal 前端 - Vue3 + TypeScript + Element Plus",
    },
    "backend": {
        "owner": "muba0321",
        "repo": "mubai-portal-api",
        "name": "mubai-portal-api",
        "description": "SRE Portal 后端 - Flask + SQLAlchemy",
    },
}

# 缓存：{url: (timestamp, data)}
_github_cache = {}
CACHE_TTL = 300  # 5 分钟缓存


def _github_get(url: str, params: dict = None) -> dict:
    """调用 GitHub API（带缓存和 Token 认证）"""
    # 检查缓存
    now = __import__("time").time()
    cache_key = f"{url}:{params}"
    if cache_key in _github_cache:
        ts, data = _github_cache[cache_key]
        if now - ts < CACHE_TTL:
            return data

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MUBAI-Portal",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    # 默认查询 main 分支的提交
    if params is None:
        params = {}
    if "sha" not in params and "commits" in url:
        params["sha"] = "main"

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            _github_cache[cache_key] = (now, data)
            return data
        if resp.status_code == 403:
            # 限流
            reset_time = resp.headers.get("X-RateLimit-Reset", "")
            logger.warning(f"GitHub API 限流，重置时间：{reset_time}")
            return {"error": "rate_limited", "message": "GitHub API 请求限流，请稍后再试"}
        logger.error(f"GitHub API 失败: {resp.status_code} {url}")
        return {}
    except Exception as e:
        logger.error(f"GitHub API 异常: {e}")
        return {}


def _get_repo_info(repo_name: str) -> dict:
    """获取仓库基本信息"""
    repo = REPOS.get(repo_name)
    if not repo:
        return {}
    return _github_get(f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}")


# ==================== 仓库概览 ====================

@git_bp.route("/repo/<repo_name>", methods=["GET"])
@jwt_required()
def get_repo(repo_name):
    """获取仓库概览信息"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在，支持 frontend/backend")

    repo = REPOS[repo_name]
    info = _get_repo_info(repo_name)

    if not info:
        return error(msg="获取仓库信息失败")

    return success(data={
        "name": repo["name"],
        "description": repo["description"],
        "github": info.get("html_url", f"https://github.com/{repo['owner']}/{repo['repo']}"),
        "totalCommits": info.get("size", 0),  # GitHub API 不直接提供提交数
        "branchCount": info.get("forks_count", 0),
        "tagCount": 0,
        "latestCommit": {
            "hash": "",
            "message": "",
            "author": "",
            "date": "",
        },
        "contributors": [],
        "stars": info.get("stargazers_count", 0),
        "forks": info.get("forks_count", 0),
        "language": info.get("language", ""),
        "updatedAt": info.get("updated_at", ""),
    })


# ==================== 提交历史 ====================

@git_bp.route("/commits/<repo_name>", methods=["GET"])
@jwt_required()
def get_commits(repo_name):
    """获取提交历史"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("pageSize", 20, type=int), 100)
    commit_type = request.args.get("type", "")
    keyword = request.args.get("keyword", "")

    params = {"page": page, "per_page": per_page}

    commits_raw = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/commits",
        params=params
    )

    if not isinstance(commits_raw, list):
        return error(msg="获取提交记录失败")

    commits = []
    for c in commits_raw:
        commit = c.get("commit", {})
        message = commit.get("message", "")
        author = commit.get("author", {}).get("name", c.get("author", {}).get("login", ""))
        date = commit.get("author", {}).get("date", "")

        # 类型筛选
        if commit_type and not message.startswith(f"{commit_type}:"):
            continue
        # 关键字筛选
        if keyword and keyword.lower() not in message.lower():
            continue

        # 解析类型
        ctype = ""
        clean_msg = message
        if ":" in message:
            prefix = message.split(":")[0].strip()
            if prefix in ("feat", "fix", "perf", "refactor", "chore", "docs", "style", "test", "ci"):
                ctype = prefix
                clean_msg = message.split(":", 1)[1].strip()

        commits.append({
            "hash": c.get("sha", "")[:7],
            "fullHash": c.get("sha", ""),
            "author": author,
            "email": commit.get("author", {}).get("email", ""),
            "date": date,
            "type": ctype,
            "message": clean_msg,
            "fullMessage": message,
        })

    return success(data={
        "list": commits,
        "total": len(commits),
        "page": page,
        "pageSize": per_page,
    })


# ==================== 提交详情 ====================

@git_bp.route("/commit/<repo_name>/<commit_hash>", methods=["GET"])
@jwt_required()
def get_commit_detail(repo_name, commit_hash):
    """获取单次提交详情"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    data = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/commits/{commit_hash}"
    )

    if not data:
        return error(msg="提交不存在")

    commit = data.get("commit", {})
    stats = data.get("stats", {})
    files = []
    for f in data.get("files", [])[:50]:
        files.append({
            "path": f.get("filename", ""),
            "added": f.get("additions", 0),
            "deleted": f.get("deletions", 0),
        })

    return success(data={
        "hash": data.get("sha", "")[:7],
        "fullHash": data.get("sha", ""),
        "author": commit.get("author", {}).get("name", ""),
        "email": commit.get("author", {}).get("email", ""),
        "date": commit.get("author", {}).get("date", ""),
        "subject": commit.get("message", "").split("\n")[0],
        "body": "\n".join(commit.get("message", "").split("\n")[1:]).strip(),
        "stats": {
            "added": stats.get("additions", 0),
            "deleted": stats.get("deletions", 0),
            "files": stats.get("total", 0),
        },
        "files": files,
    })


# ==================== 分支列表 ====================

@git_bp.route("/branches/<repo_name>", methods=["GET"])
@jwt_required()
def get_branches(repo_name):
    """获取分支列表"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    branches_raw = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/branches"
    )

    if not isinstance(branches_raw, list):
        return error(msg="获取分支列表失败")

    branches = []
    for b in branches_raw:
        name = b.get("name", "")
        commit_sha = b.get("commit", {}).get("sha", "")
        # 获取该分支最新提交信息
        commit_data = _github_get(
            f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/commits/{commit_sha}"
        )
        commit_info = commit_data.get("commit", {})
        author_info = commit_info.get("author", {})
        branches.append({
            "name": name,
            "date": author_info.get("date", "")[:10] if author_info.get("date") else "",
            "lastCommit": commit_info.get("message", "").split("\n")[0][:50] if commit_info.get("message") else "",
            "author": author_info.get("name", ""),
            "isRemote": False,
            "isMain": name in ("main", "master"),
        })

    return success(data=branches)


# ==================== Tag 列表 ====================

@git_bp.route("/tags/<repo_name>", methods=["GET"])
@jwt_required()
def get_tags(repo_name):
    """获取 Tag 列表"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    tags_raw = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/tags"
    )

    if not isinstance(tags_raw, list):
        return error(msg="获取标签列表失败")

    tags = []
    for t in tags_raw:
        name = t.get("name", "")
        commit_sha = t.get("commit", {}).get("sha", "")
        # 获取该 tag 指向的提交信息
        commit_data = _github_get(
            f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/commits/{commit_sha}"
        )
        commit_info = commit_data.get("commit", {})
        author_info = commit_info.get("author", {})
        tags.append({
            "name": name,
            "date": author_info.get("date", "")[:10] if author_info.get("date") else "",
            "message": commit_info.get("message", "").split("\n")[0][:50] if commit_info.get("message") else "",
            "author": author_info.get("name", ""),
        })

    return success(data=tags)


# ==================== 文件树 ====================

@git_bp.route("/tree/<repo_name>", methods=["GET"])
@jwt_required()
def get_tree(repo_name):
    """获取文件/目录列表"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    path = request.args.get("path", "")
    branch = request.args.get("branch", "main")

    api_path = f"contents/{path}" if path else "contents"
    data = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/{api_path}",
        params={"ref": branch}
    )

    if not data:
        return error(msg="路径不存在")

    # 单个文件
    if isinstance(data, dict) and data.get("type") == "file":
        return success(data={
            "type": "file",
            "path": data.get("path", ""),
            "name": data.get("name", ""),
        })

    # 目录
    if not isinstance(data, list):
        return error(msg="获取文件列表失败")

    items = []
    for item in data[:200]:
        items.append({
            "type": "dir" if item.get("type") == "dir" else "file",
            "name": item.get("name", ""),
            "path": item.get("path", ""),
        })

    items.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"]))

    return success(data={
        "path": path,
        "branch": branch,
        "items": items,
    })


# ==================== 文件内容 ====================

@git_bp.route("/file/<repo_name>", methods=["GET"])
@jwt_required()
def get_file_content(repo_name):
    """获取文件内容"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    path = request.args.get("path", "")
    branch = request.args.get("branch", "main")

    if not path:
        return error(msg="请指定文件路径")

    data = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/contents/{path}",
        params={"ref": branch}
    )

    if not data or not isinstance(data, dict):
        return error(msg="文件不存在")

    import base64
    content_b64 = data.get("content", "")
    try:
        content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
    except Exception:
        content = content_b64

    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "vue": "vue", "json": "json", "md": "markdown",
        "yaml": "yaml", "yml": "yaml", "sh": "bash",
        "html": "html", "css": "css", "sql": "sql",
    }

    return success(data={
        "path": path,
        "branch": branch,
        "language": lang_map.get(ext, ext),
        "content": content,
        "lines": content.count("\n") + 1 if content else 0,
    })


# ==================== Diff ====================

@git_bp.route("/diff/<repo_name>/<commit_hash>", methods=["GET"])
@jwt_required()
def get_diff(repo_name, commit_hash):
    """获取提交的代码差异"""
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    repo = REPOS[repo_name]
    data = _github_get(
        f"{GITHUB_API}/repos/{repo['owner']}/{repo['repo']}/commits/{commit_hash}"
    )

    if not data:
        return error(msg="提交不存在")

    files_diff = []
    for f in data.get("files", []):
        patch = f.get("patch", "")
        hunks = []
        current_hunk = None

        for line in patch.split("\n"):
            if line.startswith("@@"):
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {"header": line, "lines": []}
            elif current_hunk is not None:
                current_hunk["lines"].append(line)

        if current_hunk:
            hunks.append(current_hunk)

        files_diff.append({
            "path": f.get("filename", ""),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "hunks": hunks,
        })

    return success(data=files_diff)


# ==================== 网络状态检测 ====================

@git_bp.route("/network-status", methods=["GET"])
@jwt_required()
def get_network_status():
    """检测 GitHub 网络连接状态"""
    import time

    results = []
    urls_to_test = [
        {"name": "GitHub API", "url": "https://api.github.com/repos/muba0321/mubai-portal/commits?per_page=1", "timeout": 5},
        {"name": "GitHub.com", "url": "https://github.com", "timeout": 5},
    ]

    for item in urls_to_test:
        start = time.time()
        try:
            resp = requests.get(item["url"], timeout=item["timeout"])
            elapsed = round((time.time() - start) * 1000)
            results.append({
                "name": item["name"],
                "status": "connected" if resp.status_code < 400 else "error",
                "http_code": resp.status_code,
                "latency_ms": elapsed,
                "message": "连接正常" if resp.status_code < 400 else f"HTTP {resp.status_code}",
            })
        except requests.exceptions.Timeout:
            results.append({
                "name": item["name"],
                "status": "timeout",
                "http_code": 0,
                "latency_ms": item["timeout"] * 1000,
                "message": "连接超时",
            })
        except requests.exceptions.ConnectionError:
            results.append({
                "name": item["name"],
                "status": "disconnected",
                "http_code": 0,
                "latency_ms": 0,
                "message": "无法连接（网络不通或 DNS 解析失败）",
            })
        except Exception as e:
            results.append({
                "name": item["name"],
                "status": "error",
                "http_code": 0,
                "latency_ms": 0,
                "message": str(e)[:80],
            })

    # 总体状态
    all_ok = all(r["status"] == "connected" for r in results)
    any_timeout = any(r["status"] == "timeout" for r in results)

    if all_ok:
        overall = "connected"
        overall_msg = "网络连接正常"
    elif any_timeout:
        overall = "timeout"
        overall_msg = "部分连接超时，网络可能不稳定"
    else:
        overall = "disconnected"
        overall_msg = "无法连接 GitHub，请检查网络或代理配置"

    return success(data={
        "overall": overall,
        "overallMessage": overall_msg,
        "checks": results,
    })


# ==================== Blame ====================

@git_bp.route("/blame/<repo_name>", methods=["GET"])
@jwt_required()
def get_blame(repo_name):
    """获取文件 Blame 信息"""
    # GitHub API 不直接支持 blame，返回简化版本
    if repo_name not in REPOS:
        return error(msg="仓库不存在")

    path = request.args.get("path", "")
    if not path:
        return error(msg="请指定文件路径")

    return success(data={
        "path": path,
        "lines": [],
        "message": "Blame 功能需要本地 git 仓库，暂不支持",
    })
