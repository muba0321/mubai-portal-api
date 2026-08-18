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


def job_result(data, job_status):
    """根据批量作业状态返回合适的 HTTP 响应

    Args:
        data: 响应数据
        job_status: success / partial / failed
    """
    msg_map = {
        "success": "执行成功",
        "partial": "部分执行成功",
        "failed": "执行失败",
    }
    msg = msg_map.get(job_status, "执行完成")

    payload = {"code": "00000" if job_status == "success" else "20001",
               "data": _snake_to_camel(data), "msg": msg}

    if job_status == "failed":
        return jsonify(payload), 500
    return jsonify(payload)


def error(msg="系统出错", code="50000"):
    return jsonify({"code": code, "data": None, "msg": msg}), 400


def page_result(total, items):
    return {"total": total, "list": items}
