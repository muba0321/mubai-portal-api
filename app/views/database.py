import json
import re
import urllib.request
import urllib.error

from flask import Blueprint, current_app, request
from flask_jwt_extended import jwt_required
from sqlalchemy import text

from app.extensions import db
from app.utils.response import success, error, page_result

database_bp = Blueprint("database", __name__)

# 允许的 SQL 语句前缀（只读操作）
ALLOWED_PREFIXES = ("SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "DESC")


def _is_safe_sql(sql: str) -> bool:
    """校验 SQL 是否只允许读操作"""
    if not sql or not sql.strip():
        return False
    first_word = sql.strip().split()[0].upper()
    return first_word in ALLOWED_PREFIXES


def _get_engine():
    """获取底层数据库引擎/连接"""
    return db.engine


def _parse_db_url():
    """从配置中解析数据库连接信息"""
    url = db.engine.url
    return {
        "type": url.get_backend_name(),
        "host": url.host or "localhost",
        "port": url.port or 3306,
        "user": url.username or "",
        "database": url.database or "",
    }


def _get_all_tables_with_columns(database: str):
    """获取指定数据库所有表的结构，用于 NL-to-SQL 匹配"""
    try:
        result = db.session.execute(text(f"SHOW TABLES FROM `{database}`"))
        tables = [row[0] for row in result.fetchall()]
        schema = {}
        for table in tables:
            col_result = db.session.execute(
                text(f"DESCRIBE `{database}`.`{table}`")
            )
            schema[table] = [row[0] for row in col_result.fetchall()]
        return schema
    except Exception:
        return {}


@database_bp.route("/databases", methods=["GET"])
@jwt_required()
def get_databases():
    """列出所有数据库"""
    try:
        result = db.session.execute(text("SHOW DATABASES"))
        databases = [row[0] for row in result.fetchall()
                     if row[0] not in ("information_schema", "performance_schema", "mysql", "sys")]
        return success(data=databases)
    except Exception as e:
        return error(msg=f"获取数据库列表失败: {str(e)}")


@database_bp.route("/tables", methods=["GET"])
@jwt_required()
def get_tables():
    """列出指定数据库的表"""
    database = request.args.get("database", "")
    if not database:
        conn_info = _parse_db_url()
        database = conn_info["database"]

    try:
        result = db.session.execute(text(f"SHOW TABLES FROM `{database}`"))
        tables = [row[0] for row in result.fetchall()]
        return success(data=tables)
    except Exception as e:
        return error(msg=f"获取表列表失败: {str(e)}")


@database_bp.route("/tables/<table_name>/columns", methods=["GET"])
@jwt_required()
def get_table_columns(table_name: str):
    """获取表结构"""
    database = request.args.get("database", "")
    if not database:
        conn_info = _parse_db_url()
        database = conn_info["database"]

    try:
        result = db.session.execute(
            text(f"DESCRIBE `{database}`.`{table_name}`")
        )
        columns = []
        for row in result.fetchall():
            columns.append({
                "field": row[0],
                "type": row[1],
                "null": row[2],
                "key": row[3],
                "default": row[4],
                "extra": row[5],
            })
        return success(data=columns)
    except Exception as e:
        return error(msg=f"获取表结构失败: {str(e)}")


@database_bp.route("/tables/<table_name>/data", methods=["GET"])
@jwt_required()
def get_table_data(table_name: str):
    """分页获取表数据"""
    database = request.args.get("database", "")
    if not database:
        conn_info = _parse_db_url()
        database = conn_info["database"]

    page_num = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("PageSize", 20, type=int)
    page_size = min(page_size, 500)  # 限制最大条数

    try:
        offset = (page_num - 1) * page_size
        total_result = db.session.execute(
            text(f"SELECT COUNT(*) FROM `{database}`.`{table_name}`")
        )
        total = total_result.scalar()

        data_result = db.session.execute(
            text(f"SELECT * FROM `{database}`.`{table_name}` LIMIT {offset}, {page_size}")
        )
        cursor = data_result.cursor
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = []
        for row in data_result.fetchall():
            rows.append(dict(zip(columns, row)))

        return success(data=page_result(total, rows))
    except Exception as e:
        return error(msg=f"获取表数据失败: {str(e)}")


@database_bp.route("/query", methods=["POST"])
@jwt_required()
def execute_query():
    """执行 SQL 查询（仅允许 SELECT/SHOW/DESCRIBE）"""
    data = request.get_json()
    sql = (data or {}).get("sql", "").strip()

    if not sql:
        return error(msg="SQL 语句不能为空", code="40001")

    if not _is_safe_sql(sql):
        return error(msg="仅允许执行 SELECT/SHOW/DESCRIBE/EXPLAIN 查询语句", code="40003")

    # 防止多语句攻击
    if ";" in sql.rstrip(";").replace(";", "") != sql.rstrip(";"):
        return error(msg="不支持多语句执行", code="40002")

    try:
        result = db.session.execute(text(sql))
        if result.returns_rows:
            # Use cursor description for full column names
            cursor = result.cursor
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = []
            for row in result.fetchall():
                rows.append(dict(zip(columns, row)))
            return success(data={
                "columns": columns,
                "rows": rows,
                "total": len(rows),
            })
        else:
            return success(data={"affected_rows": result.rowcount})
    except Exception as e:
        return error(msg=f"SQL 执行失败: {str(e)}")


@database_bp.route("/connection-info", methods=["GET"])
@jwt_required()
def get_connection_info():
    """获取当前数据库连接信息"""
    try:
        info = _parse_db_url()
        # 获取数据库版本
        version_result = db.session.execute(text("SELECT VERSION()"))
        info["version"] = version_result.scalar()
        return success(data=info)
    except Exception as e:
        return error(msg=f"获取连接信息失败: {str(e)}")


@database_bp.route("/create", methods=["POST"])
@jwt_required()
def create_database():
    """创建新数据库"""
    data = request.get_json() or {}
    name = data.get("name", "").strip()

    if not name:
        return error(msg="数据库名称不能为空", code="40001")

    # 校验名称：字母、数字、下划线，不能以数字开头
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        return error(msg="数据库名称只能包含字母、数字和下划线，且不能以数字开头", code="40002")

    charset = data.get("charset", "utf8mb4")
    collation = data.get("collation", "utf8mb4_general_ci")

    try:
        db.session.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET {charset} COLLATE {collation}"))
        db.session.commit()
        return success(data={"name": name}, msg=f"数据库 {name} 创建成功")
    except Exception as e:
        return error(msg=f"创建数据库失败: {str(e)}")


@database_bp.route("/nl-to-sql", methods=["POST"])
@jwt_required()
def nl_to_sql():
    """自然语言转 SQL（AI 模型）"""
    data = request.get_json() or {}
    text_input = data.get("text", "").strip()
    database = data.get("database", "")

    if not text_input:
        return error(msg="查询描述不能为空", code="40001")

    if not database:
        conn_info = _parse_db_url()
        database = conn_info["database"]

    try:
        schema = _get_all_tables_with_columns(database)
        sql, explanation = _call_ai_for_sql(text_input, schema, database)
        # 安全校验
        if sql and not _is_safe_sql(sql):
            return error(msg="AI 生成的 SQL 不符合只读要求，请重新描述", code="40003")
        return success(data={"sql": sql, "explanation": explanation})
    except Exception as e:
        return error(msg=f"生成 SQL 失败: {str(e)}")


def _call_ai_for_sql(text_input: str, schema: dict, database: str) -> tuple:
    """调用 AI 模型生成 SQL"""
    # 构建 schema 描述
    schema_desc = ""
    for table, columns in schema.items():
        schema_desc += f"表名: {table}，列: {', '.join(columns)}\n"

    prompt = f"""你是一个专业的 MySQL DBA，根据用户的中文描述生成对应的 SQL。

数据库: {database}
表结构:
{schema_desc}

用户描述: {text_input}

规则:
1. 只读操作：SELECT / DESC / DESCRIBE / SHOW / EXPLAIN
2. 如果用户说"查看表结构/字段/列信息"，用 DESC 或 DESCRIBE
3. 如果用户说"查询/列出/找出"，用 SELECT
4. SELECT 查询中优先选择有意义的字段，避免 SELECT *（除非用户明确要求"所有"或"全部"）
5. 使用 MySQL 语法，只返回纯 SQL，不要解释
"""

    # 获取 API 配置
    api_key = current_app.config.get("AI_API_KEY", "")
    model = current_app.config.get("AI_MODEL", "qwen-coder-plus")

    if not api_key:
        # 无 API Key 时降级为规则生成
        return _fallback_rule_sql(text_input, schema)

    # 调用 DashScope API
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "model": model,
        "input": {
            "messages": [
                {"role": "system", "content": "你是一个专业的 MySQL DBA。根据用户的中文描述生成 MySQL 只读 SQL。只返回纯 SQL，不要任何解释。"},
                {"role": "user", "content": prompt},
            ]
        },
        "parameters": {
            "temperature": 0.1,
            "max_tokens": 512,
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # 解析返回内容
        if "output" in result and "text" in result["output"]:
            sql = result["output"]["text"].strip()
        elif "output" in result and "choices" in result["output"]:
            sql = result["output"]["choices"][0].get("message", {}).get("content", "").strip()
        else:
            raise Exception(f"API 返回格式异常: {result}")

        # 清理 Markdown 代码块
        sql = re.sub(r"^```(?:sql)?\s*", "", sql)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip()

        # 如果 AI 返回了说明文字，也一并返回
        explanation = result.get("output", {}).get("text", "")

        return sql, f"AI 模型生成 ({model})"

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise Exception(f"DashScope API 错误 ({e.code}): {err_body}")
    except urllib.error.URLError as e:
        raise Exception(f"无法连接 DashScope API: {e.reason}")


def _fallback_rule_sql(text: str, schema: dict) -> tuple:
    """AI 不可用时的规则降级（简化版）"""
    text_lower = text.lower()
    table = ""
    for t in schema:
        if t.lower() in text_lower or t.replace("_", "") in text_lower:
            table = t
            break
    if not table:
        # 关键词映射
        for t in schema:
            tl = t.lower()
            if "user" in tl and "用户" in text_lower:
                table = t; break
            if "vm" in tl and ("虚拟" in text_lower or "机器" in text_lower):
                table = t; break

    if not table:
        return "", "AI 服务不可用，且无法匹配到相关表"
    return f"SELECT * FROM `{table}`", "规则降级生成"
