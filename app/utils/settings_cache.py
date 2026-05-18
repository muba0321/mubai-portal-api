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
    from app.models.config_entry import ConfigEntry
    clear()
    for c in db_session.query(ConfigEntry.config_key, ConfigEntry.config_value).all():
        if c.config_value is not None:
            _cache[c.config_key] = c.config_value


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
