"""
测试管理 API
"""
import json
import time
from datetime import datetime, timedelta

import requests as req_lib
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, distinct

from app.extensions import db
from app.utils.response import success, error
from app.models.test_case import TestCase, TestCaseRequirementMap, TestExecution, TestExecutionStep
from app.models.requirement import Requirement, Project

test_case_bp = Blueprint("test_case", __name__)


def _get_current_user():
    try:
        return get_jwt_identity()
    except:
        return "mubai"


# ==================== 用例 CRUD ====================

@test_case_bp.route("/", methods=["GET"])
@jwt_required()
def list_test_cases():
    """用例列表"""
    project_id = request.args.get("projectId", type=int)
    test_type = request.args.get("type", "")
    priority = request.args.get("priority", "")
    status = request.args.get("status", "")
    keyword = request.args.get("keyword", "")

    q = TestCase.query
    if project_id:
        q = q.filter_by(project_id=project_id)
    if test_type:
        q = q.filter_by(test_type=test_type)
    if priority:
        q = q.filter_by(priority=priority)
    if status:
        q = q.filter_by(status=status)
    if keyword:
        q = q.filter(TestCase.title.like(f"%{keyword}%"))

    cases = q.order_by(TestCase.created_at.desc()).all()
    return success(data=[_case_to_dict(c) for c in cases])


@test_case_bp.route("/", methods=["POST"])
@jwt_required()
def create_test_case():
    """创建用例"""
    data = request.get_json()
    if not data or not data.get("title"):
        return error(msg="标题不能为空")

    case = TestCase(
        project_id=data["projectId"],
        title=data["title"],
        description=data.get("description", ""),
        test_type=data.get("testType", "manual"),
        priority=data.get("priority", "P2"),
        status=data.get("status", "draft"),
        tags=data.get("tags", []),
        api_method=data.get("apiMethod"),
        api_url=data.get("apiUrl"),
        api_headers=data.get("apiHeaders"),
        api_body=data.get("apiBody"),
        api_expected_status=data.get("apiExpectedStatus"),
        api_expected_body=data.get("apiExpectedBody"),
        manual_steps=data.get("manualSteps"),
        preconditions=data.get("preconditions"),
        created_by=_get_current_user(),
    )
    db.session.add(case)
    db.session.flush()

    # 关联需求
    req_ids = data.get("requirementIds", [])
    for rid in req_ids:
        link = TestCaseRequirementMap(test_case_id=case.id, requirement_id=rid)
        db.session.add(link)

    db.session.commit()
    return success(data={"id": case.id}, msg="创建成功")


@test_case_bp.route("/<int:case_id>", methods=["GET"])
@jwt_required()
def get_test_case(case_id):
    """获取用例详情"""
    case = TestCase.query.get(case_id)
    if not case:
        return error(msg="用例不存在")
    return success(data=_case_to_dict(case, full=True))


@test_case_bp.route("/<int:case_id>", methods=["PUT"])
@jwt_required()
def update_test_case(case_id):
    """更新用例"""
    case = TestCase.query.get(case_id)
    if not case:
        return error(msg="用例不存在")

    data = request.get_json()
    for field in ["title", "description", "testType", "priority", "status", "tags",
                  "apiMethod", "apiUrl", "apiHeaders", "apiBody",
                  "apiExpectedStatus", "apiExpectedBody", "manualSteps", "preconditions"]:
        if field in data:
            db_field = {
                "testType": "test_type", "apiMethod": "api_method", "apiUrl": "api_url",
                "apiHeaders": "api_headers", "apiBody": "api_body",
                "apiExpectedStatus": "api_expected_status", "apiExpectedBody": "api_expected_body",
                "manualSteps": "manual_steps",
            }.get(field, field)
            setattr(case, db_field, data[field])

    # 更新需求关联
    if "requirementIds" in data:
        TestCaseRequirementMap.query.filter_by(test_case_id=case_id).delete()
        for rid in data["requirementIds"]:
            link = TestCaseRequirementMap(test_case_id=case_id, requirement_id=rid)
            db.session.add(link)

    db.session.commit()
    return success(msg="更新成功")


@test_case_bp.route("/<int:case_id>", methods=["DELETE"])
@jwt_required()
def delete_test_case(case_id):
    """删除用例"""
    case = TestCase.query.get(case_id)
    if not case:
        return error(msg="用例不存在")
    db.session.delete(case)
    db.session.commit()
    return success(msg="删除成功")


# ==================== 需求关联 ====================

@test_case_bp.route("/<int:case_id>/requirements", methods=["GET"])
@jwt_required()
def get_case_requirements(case_id):
    """获取用例关联的需求"""
    links = TestCaseRequirementMap.query.filter_by(test_case_id=case_id).all()
    req_ids = [l.requirement_id for l in links]
    reqs = Requirement.query.filter(Requirement.id.in_(req_ids)).all()
    return success(data=[{
        "id": r.id, "title": r.title, "projectId": r.project_id, "status": r.status,
    } for r in reqs])


@test_case_bp.route("/<int:case_id>/requirements", methods=["POST"])
@jwt_required()
def add_case_requirement(case_id):
    """关联需求"""
    data = request.get_json()
    req_id = data.get("requirementId")
    if not req_id:
        return error(msg="需求 ID 不能为空")

    existing = TestCaseRequirementMap.query.filter_by(
        test_case_id=case_id, requirement_id=req_id
    ).first()
    if existing:
        return success(msg="已关联")

    link = TestCaseRequirementMap(test_case_id=case_id, requirement_id=req_id)
    db.session.add(link)
    db.session.commit()
    return success(msg="关联成功")


@test_case_bp.route("/<int:case_id>/requirements/<int:req_id>", methods=["DELETE"])
@jwt_required()
def remove_case_requirement(case_id, req_id):
    """取消关联需求"""
    TestCaseRequirementMap.query.filter_by(
        test_case_id=case_id, requirement_id=req_id
    ).delete()
    db.session.commit()
    return success(msg="取消关联成功")


# ==================== 测试执行 ====================

@test_case_bp.route("/<int:case_id>/execute", methods=["POST"])
@jwt_required()
def execute_test_case(case_id):
    """执行测试"""
    case = TestCase.query.get(case_id)
    if not case:
        return error(msg="用例不存在")

    data = request.get_json() or {}

    if case.test_type == "api":
        result = _execute_api_test(case)
    else:
        result = _record_manual_test(case, data)

    # 保存执行记录
    execution = TestExecution(
        test_case_id=case_id,
        executor=_get_current_user(),
        result=result["result"],
        actual_response=result.get("actual_response", ""),
        notes=data.get("notes", ""),
        environment=data.get("environment", "dev"),
        duration_ms=result.get("duration_ms", 0),
    )
    db.session.add(execution)
    db.session.flush()

    # 保存手工测试步骤结果
    if case.test_type == "manual" and "stepResults" in data:
        for step in data["stepResults"]:
            exec_step = TestExecutionStep(
                execution_id=execution.id,
                step_index=step.get("stepIndex", 0),
                status=step.get("status", "skip"),
                actual_result=step.get("actualResult", ""),
                notes=step.get("notes", ""),
            )
            db.session.add(exec_step)

    db.session.commit()
    return success(data={
        "executionId": execution.id,
        "result": result["result"],
        "durationMs": result.get("duration_ms", 0),
        "details": result.get("details", {}),
    }, msg="执行完成")


@test_case_bp.route("/<int:case_id>/executions", methods=["GET"])
@jwt_required()
def get_executions(case_id):
    """获取执行历史"""
    executions = TestExecution.query.filter_by(test_case_id=case_id).order_by(
        TestExecution.executed_at.desc()
    ).limit(50).all()
    return success(data=[{
        "id": e.id, "result": e.result, "executor": e.executor,
        "environment": e.environment, "durationMs": e.duration_ms,
        "notes": e.notes, "executedAt": e.executed_at.strftime("%Y-%m-%d %H:%M:%S"),
    } for e in executions])


# ==================== 统计 ====================

@test_case_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    """统计概览"""
    project_id = request.args.get("projectId", type=int)

    # 总用例数
    q = TestCase.query
    if project_id:
        q = q.filter_by(project_id=project_id)
    total = q.count()

    # 按状态统计
    status_counts = dict(db.session.query(
        TestCase.status, func.count(TestCase.id)
    ).group_by(TestCase.status).all())

    # 按类型统计
    type_counts = dict(db.session.query(
        TestCase.test_type, func.count(TestCase.id)
    ).group_by(TestCase.test_type).all())

    # 最近执行通过率
    recent_exec = TestExecution.query.filter(
        TestExecution.executed_at >= datetime.now() - timedelta(days=7)
    ).all()
    pass_count = sum(1 for e in recent_exec if e.result == "pass")
    total_exec = len(recent_exec)
    pass_rate = round(pass_count / total_exec * 100, 1) if total_exec > 0 else 0

    # 按项目覆盖率
    projects = Project.query.filter_by(status="active").all()
    coverage = []
    for p in projects:
        total_reqs = Requirement.query.filter_by(
            project_id=p.id, deleted_at=None
        ).count()
        covered_reqs = db.session.query(distinct(Requirement.id)).join(
            TestCaseRequirementMap,
            TestCaseRequirementMap.requirement_id == Requirement.id
        ).join(
            TestCase,
            TestCase.id == TestCaseRequirementMap.test_case_id
        ).filter(
            Requirement.project_id == p.id,
            Requirement.deleted_at == None
        ).count()
        coverage.append({
            "project": p.name,
            "total": total_reqs,
            "covered": covered_reqs,
            "rate": round(covered_reqs / total_reqs * 100, 1) if total_reqs > 0 else 0,
        })

    # 近 30 天执行趋势
    trend = []
    for i in range(29, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        count = TestExecution.query.filter(
            TestExecution.executed_at >= day_start,
            TestExecution.executed_at <= day_end
        ).count()
        trend.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    return success(data={
        "total": total,
        "statusCounts": status_counts,
        "typeCounts": type_counts,
        "passRate": pass_rate,
        "recentExecutions": total_exec,
        "coverage": coverage,
        "trend": trend,
    })


# ==================== 辅助函数 ====================

def _case_to_dict(case, full=False):
    d = {
        "id": case.id,
        "projectId": case.project_id,
        "title": case.title,
        "description": case.description,
        "testType": case.test_type,
        "priority": case.priority,
        "status": case.status,
        "tags": case.tags or [],
        "createdBy": case.created_by,
        "createdAt": case.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updatedAt": case.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if full:
        d.update({
            "apiMethod": case.api_method,
            "apiUrl": case.api_url,
            "apiHeaders": case.api_headers,
            "apiBody": case.api_body,
            "apiExpectedStatus": case.api_expected_status,
            "apiExpectedBody": case.api_expected_body,
            "manualSteps": case.manual_steps,
            "preconditions": case.preconditions,
        })
    return d


def _execute_api_test(case):
    """执行 API 测试"""
    start_time = time.time()
    try:
        resp = req_lib.request(
            method=case.api_method or "GET",
            url=case.api_url,
            headers=case.api_headers or {},
            data=case.api_body,
            timeout=30,
        )
        duration = int((time.time() - start_time) * 1000)

        status_match = resp.status_code == (case.api_expected_status or 200)

        body_match = True
        if case.api_expected_body:
            try:
                expected = json.loads(case.api_expected_body)
                actual = resp.json()
                body_match = _deep_match(expected, actual)
            except:
                body_match = False

        result = "pass" if (status_match and body_match) else "fail"
        return {
            "result": result,
            "actual_response": resp.text[:5000],
            "duration_ms": duration,
            "details": {
                "status_match": status_match,
                "body_match": body_match,
                "expected_status": case.api_expected_status,
                "actual_status": resp.status_code,
            },
        }
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        return {
            "result": "fail",
            "actual_response": str(e),
            "duration_ms": duration,
        }


def _record_manual_test(case, data):
    """记录手工测试结果"""
    step_results = data.get("stepResults", [])
    all_pass = all(s.get("status") == "pass" for s in step_results)
    return {
        "result": "pass" if all_pass else "fail",
        "actual_response": json.dumps(step_results, ensure_ascii=False),
        "duration_ms": data.get("durationMs", 0),
        "details": {"stepResults": step_results},
    }


def _deep_match(expected, actual):
    """深度匹配 JSON 对象"""
    if isinstance(expected, dict):
        for key, val in expected.items():
            if key not in actual:
                return False
            if not _deep_match(val, actual[key]):
                return False
        return True
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return False
        return all(_deep_match(e, a) for e, a in zip(expected, actual))
    else:
        return expected == actual
