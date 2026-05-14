import re

from flask import Blueprint, request
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
    """自然语言转 SQL（规则匹配）"""
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
        sql, explanation = _generate_sql(text_input, schema)
        return success(data={"sql": sql, "explanation": explanation})
    except Exception as e:
        return error(msg=f"生成 SQL 失败: {str(e)}")


def _generate_sql(text: str, schema: dict) -> tuple:
    """基于规则的自然语言转 SQL 生成"""
    text_lower = text.lower()

    # === 意图识别 ===
    is_count = any(kw in text_lower for kw in ["统计", "数量", "有多少", "多少", "总数", "count"])
    is_order = any(kw in text_lower for kw in ["排序", "按", "order"])
    is_top = any(kw in text_lower for kw in ["前", "top", "最多", "最高", "最低"])
    is_latest = any(kw in text_lower for kw in ["最新", "最近", "最近一次", "最后"])
    is_like = any(kw in text_lower for kw in ["包含", "含有", "like", "模糊"])
    is_distinct = any(kw in text_lower for kw in ["去重", "不重复", "distinct", "唯一"])
    is_group = any(kw in text_lower for kw in ["分组", "group", "按...统计"])

    # === 提取 LIMIT 数量 ===
    limit = None
    top_match = re.search(r"(?:前|top|最多|最少|最高|最低)?\s*(\d+)\s*(?:个|条|名|条记录|个记录)?", text_lower)
    if top_match or is_top:
        limit = int(top_match.group(1)) if top_match else 10

    # === 表匹配 ===
    table = _match_table(text_lower, schema)
    if not table:
        return "", f"未找到与查询相关的表，请指定表名。可用表：{', '.join(schema.keys())}"

    columns = schema[table]

    # === 列匹配 ===
    matched_cols = _match_columns(text_lower, columns)

    # === WHERE 条件 ===
    where_clause = _build_where(text_lower, columns)

    # === ORDER BY ===
    order_clause = _build_order(text_lower, columns)

    # === 生成 SQL ===
    # 如果用户指定了具体列且不是 COUNT 查询，用指定列；否则用 *
    has_specific_cols = bool(matched_cols) and not is_count and not is_distinct
    # 但如果只有排序相关的列被匹配，且用户没有明确提"查XX和YY"，仍然用 *
    if is_count:
        if is_group and matched_cols:
            sql = f"SELECT {matched_cols[0]}, COUNT(*) AS count FROM `{table}`"
        else:
            sql = f"SELECT COUNT(*) AS total FROM `{table}`"
    elif is_distinct and matched_cols:
        cols = ", ".join(matched_cols)
        sql = f"SELECT DISTINCT {cols} FROM `{table}`"
    elif has_specific_cols and len(matched_cols) > 1:
        cols = ", ".join(matched_cols)
        sql = f"SELECT {cols} FROM `{table}`"
    else:
        sql = f"SELECT * FROM `{table}`"

    if where_clause:
        sql += f" WHERE {where_clause}"

    if order_clause:
        sql += f" ORDER BY {order_clause}"

    if limit:
        sql += f" LIMIT {limit}"

    explanation = _build_explanation(text, sql, table, matched_cols, where_clause, order_clause, limit)
    return sql, explanation


def _match_table(text: str, schema: dict) -> str:
    """匹配最相关的表名"""
    # 关键词到表的映射（支持前缀匹配：sys_user, cmdb_vm 等）
    table_keywords = {
        "user": ["用户", "user", "admin", "管理员", "账号"],
        "vm": ["虚拟机", "vm", "服务器", "主机", "机器", "云主机", "集群"],
        "menu": ["菜单", "menu", "路由", "导航"],
        "role": ["角色", "role"],
        "permission": ["权限", "permission"],
        "log": ["日志", "log", "操作记录"],
        "cmdb": ["cmdb", "资产"],
        "dashboard": ["面板", "dashboard", "概览", "状态"],
        "common": ["常用", "common", "链接"],
        "config": ["配置", "config", "设置"],
        "token": ["token", "令牌"],
    }
    # 先尝试直接匹配
    for table in schema:
        if table.lower() in text:
            return table
        clean = table.replace("_", "").replace("-", "")
        if clean in text:
            return table
    # 通过关键词匹配：检查表名中是否包含任意关键词的 key
    for table in schema:
        table_lower = table.lower()
        for key, keywords in table_keywords.items():
            if key in table_lower:
                for kw in keywords:
                    if kw in text:
                        return table
    return ""


def _match_columns(text: str, columns: list) -> list:
    """匹配相关列名"""
    col_keywords = {
        "name": ["名称", "名字", "姓名"],
        "status": ["状态", "status"],
        "ip": ["ip", "地址"],
        "hostname": ["主机名", "hostname"],
        "created": ["创建"],
        "updated": ["更新"],
        "type": ["类型"],
        "id": ["编号"],
        "memory": ["内存", "memory"],
        "cpu": ["cpu", "处理器"],
        "disk": ["磁盘", "硬盘"],
        "os": ["系统", "os", "操作系统"],
        "cluster": ["集群"],
        "description": ["描述", "说明"],
        "password": ["密码", "password"],
        "email": ["邮箱", "email"],
        "username": ["用户名", "username"],
        "role": ["角色"],
        "path": ["路径", "path", "路由"],
        "icon": ["图标", "icon"],
    }
    matched = []
    for col in columns:
        col_lower = col.lower()
        # 直接匹配
        if col_lower in text:
            matched.append(col)
            continue
        # 关键词映射：检查列名中是否包含 key
        for key, keywords in col_keywords.items():
            if key in col_lower:
                for kw in keywords:
                    if kw in text:
                        matched.append(col)
                        break
                if col in matched:
                    break
    # 去重
    seen = set()
    result = []
    for c in matched:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result[:5]


def _build_where(text: str, columns: list) -> str:
    """构建 WHERE 条件"""
    conditions = []
    for col in columns:
        col_lower = col.lower()
        # 等于条件
        eq_match = re.search(rf"(?:{col_lower}|{col})\s*=?\s*为\s*(['一-鿿\w]+)", text)
        if eq_match:
            val = eq_match.group(1)
            conditions.append(f"`{col}` = '{val}'")
        # 包含/like 条件
        if any(kw in text for kw in [f"{col}包含", f"{col}含有"]):
            like_match = re.search(rf"{col_lower}(?:包含|含有)\s*(['一-鿿\w]+)", text)
            if like_match:
                val = like_match.group(1)
                conditions.append(f"`{col}` LIKE '%{val}%'")

    return " AND ".join(conditions)


def _build_order(text: str, columns: list) -> str:
    """构建 ORDER BY 子句"""
    col_keywords_order = {
        "created": ["创建", "创建时间"],
        "updated": ["更新", "更新时间"],
        "time": ["时间"],
        "date": ["日期"],
        "name": ["名称", "名字"],
        "memory": ["内存"],
        "cpu": ["cpu"],
        "disk": ["磁盘", "硬盘"],
        "ip": ["ip", "地址"],
        "status": ["状态"],
        "cluster": ["集群"],
    }
    # 检查是否包含排序意图词
    sort_indicators = ["按", "排序", "order"]
    if not any(kw in text for kw in sort_indicators):
        # 但如果是"最新/最近"类描述，仍需要时间排序
        if not any(kw in text for kw in ["最新", "最近", "最后"]):
            return ""

    for col in columns:
        col_lower = col.lower()
        for key, keywords in col_keywords_order.items():
            if key in col_lower:
                for kw in keywords:
                    if kw in text:
                        if "降序" in text or "倒序" in text or "从高到低" in text:
                            return f"`{col}` DESC"
                        if "升序" in text or "从低到高" in text:
                            return f"`{col}` ASC"
                        # 默认降序（最新/最大等语义）
                        return f"`{col}` DESC"
    # 时间相关默认排序
    if any(kw in text for kw in ["最新", "最近", "按时间"]):
        for col in columns:
            if any(kw in col.lower() for kw in ["time", "date", "created", "updated"]):
                return f"`{col}` DESC"
    return ""


def _build_explanation(text: str, sql: str, table: str, cols, where, order, limit) -> str:
    """生成解释说明"""
    parts = [f"查询表: {table}"]
    if cols:
        parts.append(f"查询字段: {', '.join(cols)}")
    if where:
        parts.append(f"过滤条件: {where}")
    if order:
        parts.append(f"排序: {order}")
    if limit:
        parts.append(f"限制: {limit} 条")
    return "; ".join(parts)
