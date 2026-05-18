from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.config_entry import ConfigEntry
from app.utils.response import success, error
from app.utils.settings_cache import refresh as refresh_cache
from datetime import datetime

config_bp = Blueprint("config", __name__)

# Apollo-style 预设配置数据：namespace + key-value
DEFAULTS = [
    # namespace: application — 基础站点信息
    {"ns": "application", "key": "site_title", "value": "SRE Portal", "type": "string", "remark": "站点标题"},
    {"ns": "application", "key": "site_description", "value": "SRE 运维管理平台", "type": "text", "remark": "站点描述"},
    {"ns": "application", "key": "copyright_info", "value": "© 2026 SRE Portal", "type": "string", "remark": "版权信息"},
    {"ns": "application", "key": "icp_number", "value": "", "type": "string", "remark": "ICP 备案号"},

    # namespace: feature-toggle — 功能开关
    {"ns": "feature-toggle", "key": "feature_cmdb", "value": "true", "type": "boolean", "remark": "是否展示虚拟机管理模块"},
    {"ns": "feature-toggle", "key": "feature_database", "value": "true", "type": "boolean", "remark": "是否展示数据库管理模块"},
    {"ns": "feature-toggle", "key": "feature_todo", "value": "true", "type": "boolean", "remark": "是否展示待办管理模块"},
    {"ns": "feature-toggle", "key": "feature_changelog", "value": "true", "type": "boolean", "remark": "是否展示版本记录模块"},
    {"ns": "feature-toggle", "key": "enable_nl_to_sql", "value": "true", "type": "boolean", "remark": "是否启用自然语言转 SQL"},
    {"ns": "feature-toggle", "key": "enable_dashboard", "value": "true", "type": "boolean", "remark": "是否展示首页仪表盘"},

    # namespace: backend — 后端参数
    {"ns": "backend", "key": "ai_api_key", "value": "", "type": "string", "remark": "通义千问 DashScope API Key"},
    {"ns": "backend", "key": "ai_model", "value": "qwen3.5-plus", "type": "string", "remark": "AI 模型名称"},
    {"ns": "backend", "key": "ai_timeout", "value": "90", "type": "number", "remark": "AI 超时时间(秒)"},
    {"ns": "backend", "key": "jwt_access_expires", "value": "3600", "type": "number", "remark": "Access Token 过期时间(秒)"},
    {"ns": "backend", "key": "jwt_refresh_expires", "value": "604800", "type": "number", "remark": "Refresh Token 过期时间(秒)"},
    {"ns": "backend", "key": "pagination_default_size", "value": "10", "type": "number", "remark": "分页默认条数"},
    {"ns": "backend", "key": "pagination_max_size", "value": "100", "type": "number", "remark": "分页最大条数"},

    # namespace: security — 安全策略
    {"ns": "security", "key": "password_min_length", "value": "8", "type": "number", "remark": "密码最小长度"},
    {"ns": "security", "key": "login_max_retries", "value": "5", "type": "number", "remark": "登录最大重试次数，超过后锁定账号"},
    {"ns": "security", "key": "session_timeout", "value": "1800", "type": "number", "remark": "会话超时时间(秒)"},
]


def _config_to_dict(c: ConfigEntry):
    return {
        "id": c.id,
        "namespace": c.namespace,
        "configKey": c.config_key,
        "configValue": c.config_value,
        "configType": c.config_type,
        "remark": c.remark,
        "createdAt": c.created_at,
        "updatedAt": c.updated_at,
    }


def _init_defaults():
    for item in DEFAULTS:
        exists = ConfigEntry.query.filter_by(namespace=item["ns"], config_key=item["key"]).first()
        if not exists:
            entry = ConfigEntry(
                namespace=item["ns"],
                config_key=item["key"],
                config_value=item.get("value"),
                config_type=item.get("type"),
                remark=item.get("remark"),
            )
            db.session.add(entry)
    db.session.commit()
    refresh_cache(db.session)


@config_bp.route("/public", methods=["GET"])
def get_public():
    """公开接口：返回 application + feature-toggle 命名空间（无需鉴权）"""
    entries = ConfigEntry.query.filter(
        ConfigEntry.namespace.in_(["application", "feature-toggle"])
    ).order_by(ConfigEntry.namespace, ConfigEntry.config_key).all()
    result = {}
    for e in entries:
        result[e.config_key] = _parse_value(e.config_value)
    return success(data=result)


@config_bp.route("", methods=["GET"])
@jwt_required()
def get_all():
    """获取所有配置列表（按命名空间分组返回）"""
    entries = ConfigEntry.query.order_by(ConfigEntry.namespace, ConfigEntry.config_key).all()
    return success(data=[_config_to_dict(e) for e in entries])


@config_bp.route("/ns/<namespace>", methods=["GET"])
@jwt_required()
def get_by_namespace(namespace):
    """按命名空间获取配置列表"""
    entries = ConfigEntry.query.filter_by(namespace=namespace).order_by(ConfigEntry.config_key).all()
    return success(data=[_config_to_dict(e) for e in entries])


@config_bp.route("/key/<key>", methods=["GET"])
@jwt_required()
def get_by_key(key):
    """按 key 获取单个配置值（跨命名空间查找）"""
    entry = ConfigEntry.query.filter_by(config_key=key).first()
    if not entry:
        return error(msg="配置项不存在", code="40400")
    return success(data=_config_to_dict(entry))


@config_bp.route("", methods=["POST"])
@jwt_required()
def create_config():
    """新增配置"""
    data = request.get_json() or {}
    namespace = data.get("namespace")
    config_key = data.get("configKey")
    if not namespace or not config_key:
        return error(msg="namespace 和 configKey 不能为空", code="40001")

    exists = ConfigEntry.query.filter_by(namespace=namespace, config_key=config_key).first()
    if exists:
        return error(msg="该命名空间下已存在同名配置", code="40002")

    entry = ConfigEntry(
        namespace=namespace,
        config_key=config_key,
        config_value=data.get("configValue"),
        config_type=data.get("configType", "string"),
        remark=data.get("remark"),
    )
    db.session.add(entry)
    db.session.commit()
    refresh_cache(db.session)
    return success(msg="创建成功", data=_config_to_dict(entry))


@config_bp.route("/<int:config_id>", methods=["PUT"])
@jwt_required()
def update_config(config_id):
    """更新配置"""
    entry = ConfigEntry.query.get(config_id)
    if not entry:
        return error(msg="配置项不存在", code="40400")

    data = request.get_json() or {}
    if "configValue" in data:
        entry.config_value = data["configValue"]
    if "configType" in data:
        entry.config_type = data["configType"]
    if "remark" in data:
        entry.remark = data["remark"]
    entry.updated_at = datetime.now()

    db.session.commit()
    refresh_cache(db.session)
    return success(msg="更新成功", data=_config_to_dict(entry))


@config_bp.route("/<int:config_id>", methods=["DELETE"])
@jwt_required()
def delete_config(config_id):
    """删除配置"""
    entry = ConfigEntry.query.get(config_id)
    if not entry:
        return error(msg="配置项不存在", code="40400")

    db.session.delete(entry)
    db.session.commit()
    refresh_cache(db.session)
    return success(msg="删除成功")


@config_bp.route("/init", methods=["POST"])
@jwt_required()
def init_defaults():
    """初始化预设配置"""
    _init_defaults()
    return success(msg="初始化成功")


def _parse_value(val):
    if val is None:
        return ""
    val_str = str(val)
    if val_str.lower() in ("true", "false"):
        return val_str.lower() == "true"
    try:
        return int(val_str)
    except ValueError:
        pass
    try:
        return float(val_str)
    except ValueError:
        pass
    return val_str
