from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.setting import SysSetting
from app.utils.response import success, error
from app.utils.settings_cache import refresh as refresh_cache
from datetime import datetime

setting_bp = Blueprint("setting", __name__)

# 预设配置数据
DEFAULTS = [
    # basic
    {"key": "site_title", "group": "basic", "type": "string", "value": "SRE Portal", "default": "SRE Portal", "label": "站点标题", "sort": 1},
    {"key": "site_description", "group": "basic", "type": "text", "value": "SRE 运维管理平台", "default": "SRE 运维管理平台", "label": "站点描述", "sort": 2},
    {"key": "copyright_info", "group": "basic", "type": "string", "value": "© 2026 SRE Portal", "default": "© 2026 SRE Portal", "label": "版权信息", "sort": 3},
    {"key": "icp_number", "group": "basic", "type": "string", "value": "", "default": "", "label": "ICP 备案号", "sort": 4},
    # feature
    {"key": "feature_cmdb", "group": "feature", "type": "boolean", "value": "true", "default": "true", "label": "虚拟机管理", "desc": "是否展示虚拟机管理模块", "sort": 1},
    {"key": "feature_database", "group": "feature", "type": "boolean", "value": "true", "default": "true", "label": "数据库管理", "desc": "是否展示数据库管理模块", "sort": 2},
    {"key": "feature_todo", "group": "feature", "type": "boolean", "value": "true", "default": "true", "label": "待办管理", "desc": "是否展示待办管理模块", "sort": 3},
    {"key": "feature_changelog", "group": "feature", "type": "boolean", "value": "true", "default": "true", "label": "版本记录", "desc": "是否展示版本记录模块", "sort": 4},
    {"key": "enable_nl_to_sql", "group": "feature", "type": "boolean", "value": "true", "default": "true", "label": "NL-to-SQL", "desc": "是否启用自然语言转 SQL 功能", "sort": 5},
    {"key": "enable_dashboard", "group": "feature", "type": "boolean", "value": "true", "default": "true", "label": "首页仪表盘", "desc": "是否展示首页仪表盘", "sort": 6},
    # backend
    {"key": "ai_api_key", "group": "backend", "type": "string", "value": "", "default": "", "label": "AI API Key", "desc": "通义千问 DashScope API Key", "sort": 1},
    {"key": "ai_model", "group": "backend", "type": "string", "value": "qwen3.5-plus", "default": "qwen3.5-plus", "label": "AI 模型名称", "sort": 2},
    {"key": "ai_timeout", "group": "backend", "type": "number", "value": "90", "default": "90", "label": "AI 超时时间(秒)", "sort": 3},
    {"key": "jwt_access_expires", "group": "backend", "type": "number", "value": "3600", "default": "3600", "label": "Access Token 过期时间(秒)", "sort": 4},
    {"key": "jwt_refresh_expires", "group": "backend", "type": "number", "value": "604800", "default": "604800", "label": "Refresh Token 过期时间(秒)", "sort": 5},
    {"key": "pagination_default_size", "group": "backend", "type": "number", "value": "10", "default": "10", "label": "分页默认条数", "sort": 6},
    {"key": "pagination_max_size", "group": "backend", "type": "number", "value": "100", "default": "100", "label": "分页最大条数", "sort": 7},
    # security
    {"key": "password_min_length", "group": "security", "type": "number", "value": "8", "default": "8", "label": "密码最小长度", "sort": 1},
    {"key": "login_max_retries", "group": "security", "type": "number", "value": "5", "default": "5", "label": "登录最大重试次数", "desc": "超过此次数后锁定账号", "sort": 2},
    {"key": "session_timeout", "group": "security", "type": "number", "value": "1800", "default": "1800", "label": "会话超时时间(秒)", "sort": 3},
]


def _setting_to_dict(s: SysSetting):
    return {
        "id": s.id,
        "settingKey": s.setting_key,
        "settingGroup": s.setting_group,
        "settingType": s.setting_type,
        "settingValue": s.setting_value,
        "defaultValue": s.default_value,
        "label": s.label,
        "description": s.description,
        "sortOrder": s.sort_order,
        "createdAt": s.created_at,
        "updatedAt": s.updated_at,
    }


def _init_defaults():
    """初始化预设配置（幂等）"""
    for item in DEFAULTS:
        exists = SysSetting.query.filter_by(setting_key=item["key"]).first()
        if not exists:
            setting = SysSetting(
                setting_key=item["key"],
                setting_group=item["group"],
                setting_type=item["type"],
                setting_value=item.get("value"),
                default_value=item.get("default"),
                label=item["label"],
                description=item.get("desc"),
                sort_order=item["sort"],
            )
            db.session.add(setting)
    db.session.commit()
    refresh_cache(db.session)


@setting_bp.route("/public", methods=["GET"])
def get_public():
    """公开接口：返回基础信息 + 功能开关（无需鉴权）"""
    settings = SysSetting.query.filter(
        SysSetting.setting_group.in_(["basic", "feature"])
    ).order_by(SysSetting.sort_order).all()
    result = {}
    for s in settings:
        result[s.setting_key] = _parse_value(s.setting_value)
    return success(data=result)


@setting_bp.route("/group/<group>", methods=["GET"])
@jwt_required()
def get_by_group(group):
    """按分组获取配置列表"""
    settings = SysSetting.query.filter_by(setting_group=group).order_by(SysSetting.sort_order).all()
    return success(data=[_setting_to_dict(s) for s in settings])


@setting_bp.route("/key/<key>", methods=["GET"])
@jwt_required()
def get_by_key(key):
    """按 key 获取单个配置值"""
    setting = SysSetting.query.filter_by(setting_key=key).first()
    if not setting:
        return error(msg="配置项不存在", code="40400")
    return success(data=_setting_to_dict(setting))


@setting_bp.route("", methods=["PUT"])
@jwt_required()
def update_batch():
    """批量更新配置 {key: value, ...}"""
    data = request.get_json() or {}
    if not data:
        return error(msg="请求体不能为空", code="40001")

    updated_keys = []
    for key, value in data.items():
        setting = SysSetting.query.filter_by(setting_key=key).first()
        if not setting:
            continue
        setting.setting_value = str(value) if value is not None else ""
        setting.updated_at = datetime.now()
        updated_keys.append(key)

    db.session.commit()
    refresh_cache(db.session)
    return success(msg="保存成功", data={"updatedKeys": updated_keys})


@setting_bp.route("/init", methods=["POST"])
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
