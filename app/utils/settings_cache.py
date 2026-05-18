"""系统配置内存缓存，避免每次请求查数据库。"""

_cache: dict[str, str] = {}


def get(key: str, default=None):
    val = _cache.get(key)
    return default if val is None else _parse_value(val)


def set(key: str, value):
    _cache[key] = str(value)


def clear():
    _cache.clear()


def refresh(db_session):
    from app.models.setting import SysSetting
    clear()
    for s in db_session.query(SysSetting.setting_key, SysSetting.setting_value).all():
        if s.setting_value is not None:
            _cache[s.setting_key] = s.setting_value


def _parse_value(val: str):
    """尝试将字符串值转为合适类型"""
    if val.lower() in ("true", "false"):
        return val.lower() == "true"
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val
