import json
import re
import time
import requests
from urllib import request as urllib_request
from functools import wraps
from flask import Blueprint, request, current_app, jsonify
from flask_jwt_extended import jwt_required, decode_token
from app.config import Config
from app.utils.response import success, error

grafana_bp = Blueprint("grafana", __name__)

# Grafana 配置
GRAFANA_URL = getattr(Config, "GRAFANA_URL", "http://45.205.31.249:3001")
GRAFANA_API_KEY = getattr(Config, "GRAFANA_API_KEY", "")

# 任务存储（内存，开发环境够用）
_task_store: dict[str, dict] = {}


def jwt_from_query():
    """SSE 端点专用鉴权：从 URL 查询参数读取 token（EventSource 不支持自定义 header）"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = request.args.get("token", "")
            if not token:
                return Response(
                    jsonify({"code": "40100", "data": None, "msg": "缺少 token"}).get_data(),
                    status=401, content_type="application/json"
                )
            try:
                # 直接解码 token，不依赖 headers 配置
                decode_token(token)
            except Exception as e:
                return Response(
                    jsonify({"code": "40101", "data": None, "msg": f"token 无效或已过期: {str(e)}"}).get_data(),
                    status=401, content_type="application/json"
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


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


def _sse_event(data, event=None, event_id=None):
    """格式化为 SSE 事件"""
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


# ==================== 任务管道 ====================

# 定义子任务
SUB_TASKS = [
    {"id": "parse", "name": "解析需求", "icon": "📋"},
    {"id": "fetch_dashboard", "name": "获取仪表盘信息", "icon": ""},
    {"id": "fetch_metrics", "name": "获取可用指标", "icon": ""},
    {"id": "ai_generate", "name": "AI 生成面板配置", "icon": "🤖"},
    {"id": "validate", "name": "验证结果", "icon": "✅"},
    {"id": "done", "name": "完成", "icon": "🎉"},
]


def _run_task_pipeline(task_id: str, params: dict):
    """执行任务管道，推送 SSE 事件到 task store"""
    import logging
    logger = logging.getLogger("sre-portal")

    try:
        _run_task_pipeline_inner(task_id, params, logger)
    except Exception as e:
        logger.error(f"[Task {task_id}] UNCAUGHT EXCEPTION: {type(e).__name__}: {e}")
        task = _task_store.get(task_id)
        if task:
            task["status"] = "error"
            task["last_event"] = _sse_event({"status": "error", "message": f"Pipeline 异常: {str(e)}"}, event="task-error")


def _run_task_pipeline_inner(task_id: str, params: dict, logger):
    """执行任务管道内部逻辑"""
    logger.info(f"[Task {task_id}] Pipeline started")

    dashboard_uid = params.get("dashboard_uid", "")
    panel_id = params.get("panel_id")
    description = params.get("description", "")
    operation = params.get("operation", "add")

    task = _task_store.get(task_id)
    if not task:
        logger.error(f"[Task {task_id}] Task not found in store")
        return

    def _report(step_id, status, message="", data=None):
        task["steps"][step_id] = {"status": status, "message": message, "data": data}
        task["last_event"] = _sse_event({
            "stepId": step_id,
            "status": status,
            "message": message,
            "data": data,
        }, event="task-progress")
        logger.info(f"[Task {task_id}] Step {step_id}: {status} - {message}")

    # Step 1: 解析需求
    _report("parse", "running", f"正在解析: {description[:50]}...")
    time.sleep(0.2)
    _report("parse", "done", f"已识别操作: {operation}")

    # Step 2: 获取仪表盘信息
    _report("fetch_dashboard", "running", "正在获取仪表盘元数据...")
    dashboard_info = {}
    if dashboard_uid:
        code, dash_data = _grafana_request("GET", f"dashboards/uid/{dashboard_uid}")
        if code == 200:
            dashboard_info = dash_data.get("dashboard", {})
            _report("fetch_dashboard", "done", f"仪表盘: {dashboard_info.get('title', '未知')}，{len(dashboard_info.get('panels', []))} 个面板")
        else:
            _report("fetch_dashboard", "error", f"获取仪表盘失败: {dash_data}")
            task["status"] = "error"
            return
    else:
        _report("fetch_dashboard", "done", "无仪表盘，将创建新面板配置")

    dashboard = dashboard_info
    template_vars = dashboard.get("templating", {}).get("list", [])
    template_var_names = [v.get("name", "") for v in template_vars]
    existing_panels = []
    for p in dashboard.get("panels", []):
        existing_panels.append({"id": p.get("id"), "title": p.get("title"), "type": p.get("type")})

    # 如果是 modify，获取原面板
    original_panel = None
    if operation == "modify" and panel_id is not None:
        for p in dashboard.get("panels", []):
            if p.get("id") == panel_id:
                original_panel = p
                break
        if not original_panel:
            _report("fetch_dashboard", "error", f"未找到 ID 为 {panel_id} 的面板")
            task["status"] = "error"
            return

    # Step 3: 获取 Prometheus 可用指标
    _report("fetch_metrics", "running", "正在查询 Prometheus 可用指标...")
    prom_metrics = []
    try:
        url = f"{Config.PROMETHEUS_URL}/api/v1/label/__name__/values"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            prom_metrics = [m for m in data if m.startswith(("node_", "mysql_"))][:80]
            _report("fetch_metrics", "done", f"发现 {len(prom_metrics)} 个可用指标")
    except Exception as e:
        _report("fetch_metrics", "done", f"指标查询跳过: {str(e)[:30]}")

    # Step 4: AI 生成
    logger.info(f"[Task {task_id}] Step 4: Starting AI generation...")
    _report("ai_generate", "running", "正在调用 AI 生成面板配置...")
    panel_json, err = _call_ai_for_panel(
        dashboard, description, operation, template_var_names,
        existing_panels, prom_metrics, original_panel
    )
    logger.info(f"[Task {task_id}] Step 4: AI call returned, err={err}")

    if err:
        _report("ai_generate", "error", err)
        task["status"] = "error"
        return
    _report("ai_generate", "done", "AI 生成完毕")

    # Step 5: 验证
    _report("validate", "running", "正在验证生成的面板配置...")
    validation_issues = []
    if not isinstance(panel_json, dict):
        validation_issues.append("返回格式不是 JSON 对象")
    if not panel_json.get("title"):
        validation_issues.append("缺少面板标题")
    if not panel_json.get("type"):
        validation_issues.append("缺少面板类型(type)")
    if not panel_json.get("datasource"):
        validation_issues.append("缺少 datasource 字段")
    if not panel_json.get("targets"):
        validation_issues.append("缺少查询目标(targets)")
    else:
        for t in panel_json.get("targets", []):
            if not t.get("expr"):
                validation_issues.append(f"Target {t.get('refId', '?')} 缺少 PromQL 表达式")
            if not t.get("datasource"):
                validation_issues.append(f"Target {t.get('refId', '?')} 缺少 datasource")

    if validation_issues:
        _report("validate", "warning", "验证发现问题: " + "; ".join(validation_issues), {"issues": validation_issues})
    else:
        _report("validate", "done", "配置验证通过")

    # Step 6: 完成
    explanation = ""
    if operation == "add":
        explanation = f"AI 已生成新面板：{panel_json.get('title', '未命名')}（类型：{panel_json.get('type', 'unknown')}）"
    elif operation == "modify":
        old_title = original_panel.get("title", "") if original_panel else ""
        new_title = panel_json.get("title", old_title)
        explanation = f"AI 已修改面板：{old_title} → {new_title}"
    elif operation == "delete":
        explanation = f"AI 已标记删除面板 ID {panel_id}"

    # 替换 datasource uid 为实际值（AI 生成的 uid 可能不匹配）
    if panel_json and isinstance(panel_json, dict):
        try:
            code, ds_data = _grafana_request("GET", "datasources")
            if code == 200:
                for ds in ds_data:
                    if ds.get("type") == "prometheus":
                        actual_uid = ds.get("uid")
                        if panel_json.get("datasource"):
                            panel_json["datasource"]["uid"] = actual_uid
                        for target in panel_json.get("targets", []):
                            if target.get("datasource"):
                                target["datasource"]["uid"] = actual_uid
                        break
        except Exception as e:
            logger.warning(f"[Task {task_id}] Failed to get datasource uid: {e}")

    task["result"] = {"panelJson": panel_json, "explanation": explanation, "operation": operation}
    task["status"] = "done"
    _report("done", "done", explanation)
    task["last_event"] = _sse_event({
        "result": task["result"],
        "steps": {k: {"status": v["status"], "message": v["message"]} for k, v in task["steps"].items()},
    }, event="task-complete")


def _call_ai_for_panel(dashboard, description, operation, template_var_names, existing_panels, prom_metrics, original_panel):
    """调用 DashScope AI 生成面板 JSON"""
    import logging
    logger = logging.getLogger("sre-portal")
    logger.info("[AI] Starting AI call to DashScope")

    api_key = Config.AI_API_KEY
    model = Config.AI_MODEL
    logger.info(f"[AI] API Key: {api_key[:20]}..., Model: {model}")

    if not api_key:
        return None, "AI API Key 未配置"

    PROMQL_EXAMPLES = """
常用 PromQL 指标参考：
- CPU 使用率：100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle",instance=~"$instance"}[5m])) * 100)
- 内存使用率：(1 - (node_memory_MemAvailable_bytes{instance=~"$instance"} / node_memory_MemTotal_bytes{instance=~"$instance"})) * 100
- 磁盘使用率(/)：(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/",instance=~"$instance"})) * 100
- 系统负载：node_load1{instance=~"$instance"} / node_load5 / node_load15
- 内存使用量：node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes
- 磁盘读取速率：rate(node_disk_read_bytes_total{instance=~"$instance"}[5m])
- 磁盘写入速率：rate(node_disk_written_bytes_total{instance=~"$instance"}[5m])
- 网络接收流量：rate(node_network_receive_bytes_total{device!~"lo",instance=~"$instance"}[5m])
- 网络发送流量：rate(node_network_transmit_bytes_total{device!~"lo",instance=~"$instance"}[5m])
- TCP 连接数：node_netstat_Tcp_CurrEstab{instance=~"$instance"}
- MySQL 状态：mysql_up{instance=~"$instance"}
"""

    system_prompt = (
        "你是一个 Grafana 面板配置专家。根据用户的中文描述，生成 Grafana 面板 JSON 配置。\n\n"
        "关键规则：\n"
        "1. 只返回纯 JSON，用 ```json 包裹\n"
        "2. 面板类型：gauge(仪表盘), timeseries(折线图), stat(统计卡片), bargauge(条形仪表), row(行分组)\n"
        "3. PromQL 必须使用模板变量 $instance，如 instance=~\"$instance\"\n"
        "4. 时间窗口默认 [5m]，可根据描述调整\n"
        "5. 字段单位：percent, bytes, Bps, short, s, iops\n"
        "6. 颜色阈值：green(<70) → yellow(70-90) → red(>90)\n"
        "7. 每个 target 必须有唯一的 refId (A, B, C, D...)\n"
        "\n【重要】返回的 JSON 必须是单个面板配置，必须包含以下所有字段：\n"
        "{\n"
        "  \"title\": \"面板标题\",\n"
        "  \"type\": \"timeseries\",\n"
        "  \"id\": 1,\n"
        "  \"datasource\": {\"type\": \"prometheus\", \"uid\": \"prometheus\"},\n"
        "  \"targets\": [{\"datasource\": {\"type\": \"prometheus\", \"uid\": \"prometheus\"}, \"expr\": \"promql\", \"refId\": \"A\"}],\n"
        "  \"fieldConfig\": {\"defaults\": {\"unit\": \"percent\", \"thresholds\": {\"mode\": \"absolute\", \"steps\": [{\"color\": \"green\", \"value\": null}, {\"color\": \"yellow\", \"value\": 70}, {\"color\": \"red\", \"value\": 90}]}}, \"overrides\": []},\n"
        "  \"options\": {\"legend\": {\"displayMode\": \"list\", \"placement\": \"bottom\"}, \"tooltip\": {\"mode\": \"single\", \"sort\": \"none\"}},\n"
        "  \"gridPos\": {\"h\": 8, \"w\": 12, \"x\": 0, \"y\": 0}\n"
        "}\n"
        "\n注意：\n"
        "- 不要返回 dashboard 包裹结构，只返回面板对象本身\n"
        "- datasource 的 uid 写 \"prometheus\" 即可，后端会自动替换为实际 UID\n"
        "- gridPos 的 w 总和不超过 24"
    )

    user_prompt = f"当前仪表盘信息：\n"
    user_prompt += f"- 标题：{dashboard.get('title', '未知')}\n"
    user_prompt += f"- 模板变量：{', '.join(template_var_names) if template_var_names else '无'}\n"
    user_prompt += f"- 已有面板（id, title, type）：\n"
    for ep in existing_panels:
        user_prompt += f"  - id={ep['id']}, title={ep['title']}, type={ep['type']}\n"
    user_prompt += f"- 数据源：Prometheus\n\n"

    if prom_metrics:
        user_prompt += f"Prometheus 可用指标（部分）：\n{', '.join(prom_metrics[:50])}\n\n"

    user_prompt += PROMQL_EXAMPLES + "\n"
    user_prompt += f"用户操作：{operation}\n"
    user_prompt += f"用户描述：{description}\n\n"

    if operation == "modify" and original_panel:
        user_prompt += f"原面板 JSON：\n{json.dumps(original_panel, ensure_ascii=False, indent=2)}\n\n"
        user_prompt += "请根据用户描述修改上述面板，返回修改后的完整面板 JSON。必须包含 id, title, type, datasource, targets, fieldConfig, options, gridPos 所有字段。\n"
    elif operation == "add":
        user_prompt += "请生成一个完整的面板 JSON 对象。必须严格包含以下所有字段：id, title, type, datasource, targets, fieldConfig, options, gridPos。不要省略任何字段。\n"
    elif operation == "delete":
        user_prompt += "请返回删除面板的操作 JSON，格式为 {\"action\": \"delete\", \"panel_id\": <id>}。\n"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 8192,
    }

    req = urllib_request.Request(
        "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        logger.info("[AI] Sending request to DashScope via urllib...")
        resp = urllib_request.urlopen(req, timeout=180)
        resp_data = resp.read().decode("utf-8")
        logger.info(f"[AI] Response received, length: {len(resp_data)} chars")
        result = json.loads(resp_data)
        status_code = resp.getcode()
        logger.info(f"[AI] Response status: {status_code}")

        if status_code != 200:
            error_msg = result.get("error", {}).get("message", "未知错误")
            return None, f"AI 请求失败: HTTP {status_code} - {error_msg}"

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        logger.info(f"[AI] Content received, length: {len(content)} chars")

        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        content = content.strip()

        panel_json = json.loads(content)
        logger.info("[AI] Panel JSON generated successfully")
        return panel_json, None
    except urllib_request.HTTPError as e:
        logger.error(f"[AI] HTTP Error: {e.code}")
        return None, f"AI 请求失败: HTTP {e.code}"
    except urllib_request.URLError as e:
        logger.error(f"[AI] URL Error: {e.reason}")
        return None, f"AI 请求异常: {str(e.reason)}"
    except json.JSONDecodeError:
        logger.error("[AI] JSON decode error")
        return None, "AI 返回格式不是有效的 JSON"
    except Exception as e:
        logger.error(f"[AI] Exception: {type(e).__name__}: {e}")
        return None, f"AI 调用异常: {str(e)}"


# ==================== API 端点 ====================

import uuid

@grafana_bp.route("/nl-to-panel", methods=["POST"])
@jwt_required()
def nl_to_panel_start():
    """创建并同步执行 AI 面板生成任务（AI 调用可能耗时 60-90 秒）"""
    data = request.get_json()
    if not data:
        return error(msg="请求体不能为空", code="40001")

    description = data.get("description", "").strip()
    if not description:
        return error(msg="请描述您想要的操作", code="40002")

    operation = data.get("operation", "add")
    if operation not in ("add", "modify", "delete"):
        return error(msg="operation 必须是 add/modify/delete", code="40003")

    task_id = str(uuid.uuid4())[:8]
    _task_store[task_id] = {
        "id": task_id,
        "status": "running",
        "created_at": time.time(),
        "steps": {s["id"]: {"status": "pending", "message": "", "icon": s["icon"], "name": s["name"]} for s in SUB_TASKS},
        "result": None,
        "last_event": _sse_event({"taskId": task_id, "status": "running", "steps": {s["id"]: s["name"] for s in SUB_TASKS}}, event="task-start"),
    }

    # 同步执行任务管道（AI 调用通常 60-90 秒）
    _run_task_pipeline(task_id, {
        "dashboard_uid": data.get("dashboard_uid", ""),
        "panel_id": data.get("panel_id"),
        "description": description,
        "operation": operation,
    })

    task = _task_store[task_id]
    if task["status"] == "error":
        return error(msg="AI 生成失败，请重试", code="50001")

    return success(data=task["result"], msg="AI 生成完成")


@grafana_bp.route("/nl-to-panel/<task_id>/status", methods=["GET"])
@jwt_required()
def nl_to_panel_status(task_id):
    """查询任务当前状态（轮询用）"""
    task = _task_store.get(task_id)
    if not task:
        return error(msg="任务不存在", code="40401"), 404
    return jsonify({"code": "00000", "data": {
        "status": task["status"],
        "steps": {k: {"status": v["status"], "message": v["message"]} for k, v in task["steps"].items()},
        "result": task["result"],
    }, "msg": "ok"}), 200


@grafana_bp.route("/nl-to-panel/<task_id>/stream", methods=["GET"])
@jwt_from_query()
def nl_to_panel_stream(task_id):
    """SSE 流式推送任务进度"""
    task = _task_store.get(task_id)
    if not task:
        return error(msg="任务不存在", code="40401"), 404

    def event_stream():
        last_event = ""
        # 先发送已缓存的事件
        if task.get("last_event"):
            yield task["last_event"]
            last_event = task["last_event"]

        # 持续推送直到任务完成或错误
        while True:
            current_task = _task_store.get(task_id)
            if not current_task:
                yield _sse_event({"status": "error", "message": "任务已丢失"}, event="task-error")
                break

            # 如果有新事件则推送
            if current_task.get("last_event") and current_task["last_event"] != last_event:
                yield current_task["last_event"]
                last_event = current_task["last_event"]

            if current_task["status"] in ("done", "error"):
                break

            time.sleep(0.3)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ==================== 原有端点 ====================

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
