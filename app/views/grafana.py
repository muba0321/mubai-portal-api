import json
import requests
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.config import Config
from app.utils.response import success, error

grafana_bp = Blueprint("grafana", __name__)

# Grafana 配置
GRAFANA_URL = Config.__dict__.get("GRAFANA_URL", "http://45.205.31.249:3000")
GRAFANA_API_KEY = Config.__dict__.get("GRAFANA_API_KEY", "")


def _grafana_request(method, path, **kwargs):
    """调用 Grafana HTTP API"""
    url = f"{GRAFANA_URL}/api/{path}"
    headers = {"Content-Type": "application/json"}
    if GRAFANA_API_KEY:
        headers["Authorization"] = f"Bearer {GRAFANA_API_KEY}"
    try:
        resp = requests.request(method, url, headers=headers, timeout=10, **kwargs)
        return resp.status_code, resp.json() if resp.text else {}
    except Exception as e:
        return 500, {"error": str(e)}


@grafana_bp.route("/dashboards", methods=["GET"])
@jwt_required()
def list_dashboards():
    """获取所有面板列表"""
    code, data = _grafana_request("GET", "search?query=&type=dash-db")
    if code != 200:
        return error(msg=f"获取面板列表失败: {data}", code=str(code))
    return success(data=data)


@grafana_bp.route("/dashboards/<string:uid>", methods=["GET"])
@jwt_required()
def get_dashboard(uid):
    """获取面板详情"""
    code, data = _grafana_request("GET", f"dashboards/uid/{uid}")
    if code != 200:
        return error(msg=f"获取面板失败: {data}", code=str(code))
    return success(data=data)


@grafana_bp.route("/dashboards", methods=["POST"])
@jwt_required()
def create_dashboard():
    """创建面板"""
    payload = request.get_json()
    payload["overwrite"] = True
    code, data = _grafana_request("POST", "dashboards/db", json=payload)
    if code not in (200, 202):
        return error(msg=f"创建面板失败: {data}", code=str(code))
    return success(data=data, msg="创建成功")


@grafana_bp.route("/dashboards", methods=["PUT"])
@jwt_required()
def update_dashboard():
    """更新面板"""
    payload = request.get_json()
    payload["overwrite"] = True
    code, data = _grafana_request("POST", "dashboards/db", json=payload)
    if code not in (200, 202):
        return error(msg=f"更新面板失败: {data}", code=str(code))
    return success(data=data, msg="更新成功")


@grafana_bp.route("/dashboards/<string:uid>", methods=["DELETE"])
@jwt_required()
def delete_dashboard(uid):
    """删除面板"""
    code, data = _grafana_request("DELETE", f"dashboards/uid/{uid}")
    if code != 200:
        return error(msg=f"删除面板失败: {data}", code=str(code))
    return success(msg="删除成功")


@grafana_bp.route("/datasources", methods=["GET"])
@jwt_required()
def list_datasources():
    """获取所有数据源"""
    code, data = _grafana_request("GET", "datasources")
    if code != 200:
        return error(msg=f"获取数据源失败: {data}", code=str(code))
    return success(data=data)


@grafana_bp.route("/folders", methods=["GET"])
@jwt_required()
def list_folders():
    """获取所有文件夹"""
    code, data = _grafana_request("GET", "folders")
    if code != 200:
        return error(msg=f"获取文件夹失败: {data}", code=str(code))
    return success(data=data)


@grafana_bp.route("/folders", methods=["POST"])
@jwt_required()
def create_folder():
    """创建文件夹"""
    payload = request.get_json()
    code, data = _grafana_request("POST", "folders", json=payload)
    if code not in (200, 202):
        return error(msg=f"创建文件夹失败: {data}", code=str(code))
    return success(data=data, msg="创建成功")


@grafana_bp.route("/folders/<int:folder_id>", methods=["DELETE"])
@jwt_required()
def delete_folder(folder_id):
    """删除文件夹"""
    code, data = _grafana_request("DELETE", f"folders/id/{folder_id}")
    if code != 200:
        return error(msg=f"删除文件夹失败: {data}", code=str(code))
    return success(msg="删除成功")
