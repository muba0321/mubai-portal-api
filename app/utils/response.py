import re
from datetime import datetime, date

from flask import jsonify


def _to_camel_case(snake_str):
    if snake_str is None:
        return None
    parts = snake_str.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def _snake_to_camel(obj):
    if isinstance(obj, dict):
        return {
            _to_camel_case(k): _snake_to_camel(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_snake_to_camel(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, date):
        return obj.strftime("%Y-%m-%d")
    return obj


def success(data=None, msg="一切ok"):
    return jsonify({"code": "00000", "data": _snake_to_camel(data), "msg": msg})


def error(msg="系统出错", code="50000"):
    return jsonify({"code": code, "data": None, "msg": msg}), 400


def page_result(total, items):
    return {"total": total, "list": items}
