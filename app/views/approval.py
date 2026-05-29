import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.approval import ApprovalTemplate, ApprovalRecord, ApprovalStep
from app.models.sys_user import SysUser
from app.utils.permission import success_response, error_response

approval_bp = Blueprint("approval", __name__)


def template_to_dict(t):
    return {
        "id": str(t.id),
        "name": t.name,
        "code": t.code,
        "type": t.type,
        "description": t.description or "",
        "approvers": t.get_approvers(),
        "enabled": t.enabled,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
    }


def record_to_dict(r):
    return {
        "id": str(r.id),
        "templateId": str(r.template_id),
        "templateName": r.template.name if r.template else "",
        "applicantId": str(r.applicant_id),
        "applicantName": r.applicant.username if r.applicant else "",
        "title": r.title,
        "content": r.get_content(),
        "status": r.status,
        "currentLevel": r.current_level,
        "result": r.result or "",
        "createdAt": r.created_at.isoformat() if r.created_at else None,
        "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        "steps": [step_to_dict(s) for s in r.steps],
    }


def step_to_dict(s):
    return {
        "id": str(s.id),
        "level": s.level,
        "approverId": str(s.approver_id),
        "approverName": s.approver.username if s.approver else "",
        "status": s.status,
        "comment": s.comment or "",
        "decidedAt": s.decided_at.isoformat() if s.decided_at else None,
    }


# ========== 审批模板 ==========

@approval_bp.route("/templates", methods=["GET"])
@jwt_required()
def list_templates():
    templates = ApprovalTemplate.query.filter_by(enabled=1).order_by(ApprovalTemplate.id).all()
    return success_response([template_to_dict(t) for t in templates])


@approval_bp.route("/templates", methods=["POST"])
@jwt_required()
def create_template():
    data = request.get_json()
    if ApprovalTemplate.query.filter_by(code=data["code"]).first():
        return error_response("模板编码已存在", "400")

    template = ApprovalTemplate(
        name=data["name"],
        code=data["code"],
        type=data["type"],
        description=data.get("description", ""),
        approvers=json.dumps(data.get("approvers", [])),
    )
    db.session.add(template)
    db.session.commit()
    return success_response(template_to_dict(template), "创建成功")


@approval_bp.route("/templates/<int:template_id>", methods=["PUT"])
@jwt_required()
def update_template(template_id):
    template = ApprovalTemplate.query.get_or_404(template_id)
    data = request.get_json()
    for key in ["name", "description", "enabled"]:
        if key in data:
            setattr(template, key, data[key])
    if "approvers" in data:
        template.approvers = json.dumps(data["approvers"])
    db.session.commit()
    return success_response(template_to_dict(template), "更新成功")


# ========== 审批记录 ==========

@approval_bp.route("", methods=["POST"])
@jwt_required()
def create_approval():
    """发起审批"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)

    data = request.get_json()
    template = ApprovalTemplate.query.filter_by(code=data["templateCode"]).first()
    if not template:
        return error_response("审批模板不存在", "400")

    record = ApprovalRecord(
        template_id=template.id,
        applicant_id=user_id,
        title=data.get("title", template.name),
        content=json.dumps(data.get("content", {})),
    )
    db.session.add(record)
    db.session.flush()

    # 创建审批步骤
    approvers = template.get_approvers()
    for i, approver_config in enumerate(approvers):
        # 根据配置解析审批人: role 或 user_id
        approver_id = approver_config.get("user_id")
        if not approver_id:
            # 按角色查找第一个用户
            role_code = approver_config.get("role")
            if role_code:
                from app.models.sys_role import Role
                from app.models.sys_user_role import UserRole
                role = Role.query.filter_by(code=role_code).first()
                if role:
                    ur = UserRole.query.filter_by(role_id=role.id).first()
                    approver_id = ur.user_id if ur else user_id
        if not approver_id:
            approver_id = user_id  # fallback

        step = ApprovalStep(
            approval_id=record.id,
            level=i + 1,
            approver_id=approver_id,
            status="pending" if i == 0 else "waiting",
        )
        db.session.add(step)

    db.session.commit()
    return success_response(record_to_dict(record), "审批已发起")


@approval_bp.route("", methods=["GET"])
@jwt_required()
def list_approvals():
    """我的审批列表"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)

    approval_type = request.args.get("type", "pending")  # pending/done/initiated
    page_num = request.args.get("pageNum", 1, type=int)
    page_size = request.args.get("pageSize", 10, type=int)

    if approval_type == "initiated":
        query = ApprovalRecord.query.filter_by(applicant_id=user_id)
    elif approval_type == "done":
        query = (
            ApprovalRecord.query
            .join(ApprovalStep, ApprovalStep.approval_id == ApprovalRecord.id)
            .filter(ApprovalStep.approver_id == user_id, ApprovalStep.status != "pending")
        )
    else:
        # 待我审批的
        query = (
            ApprovalRecord.query
            .join(ApprovalStep, ApprovalStep.approval_id == ApprovalRecord.id)
            .filter(ApprovalStep.approver_id == user_id, ApprovalStep.status == "pending")
        )

    total = query.distinct().count()
    records = query.order_by(ApprovalRecord.created_at.desc()).offset((page_num - 1) * page_size).limit(page_size).all()
    return success_response({"list": [record_to_dict(r) for r in records], "total": total})


@approval_bp.route("/<int:record_id>", methods=["GET"])
@jwt_required()
def get_approval(record_id):
    """审批详情"""
    record = ApprovalRecord.query.get_or_404(record_id)
    return success_response(record_to_dict(record))


@approval_bp.route("/<int:record_id>/approve", methods=["POST"])
@jwt_required()
def approve_record(record_id):
    """审批通过"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)

    data = request.get_json()
    record = ApprovalRecord.query.get_or_404(record_id)

    # 找到当前用户的审批步骤
    step = ApprovalStep.query.filter_by(
        approval_id=record_id, approver_id=user_id, status="pending"
    ).first()
    if not step:
        return error_response("您不是当前审批的审批人", "400")

    step.status = "approved"
    step.comment = data.get("comment", "")
    from datetime import datetime as dt
    step.decided_at = dt.utcnow()

    # 检查是否有下一级审批
    next_step = ApprovalStep.query.filter_by(
        approval_id=record_id, level=step.level + 1
    ).first()
    if next_step:
        next_step.status = "pending"
        record.current_level = next_step.level
    else:
        record.status = "approved"
        record.result = data.get("comment", "")

    db.session.commit()
    return success_response(record_to_dict(record), "审批通过")


@approval_bp.route("/<int:record_id>/reject", methods=["POST"])
@jwt_required()
def reject_record(record_id):
    """审批驳回"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)

    data = request.get_json()
    record = ApprovalRecord.query.get_or_404(record_id)

    step = ApprovalStep.query.filter_by(
        approval_id=record_id, approver_id=user_id, status="pending"
    ).first()
    if not step:
        return error_response("您不是当前审批的审批人", "400")

    step.status = "rejected"
    step.comment = data.get("comment", "")
    from datetime import datetime as dt
    step.decided_at = dt.utcnow()

    record.status = "rejected"
    record.result = data.get("comment", "")

    db.session.commit()
    return success_response(record_to_dict(record), "已驳回")


@approval_bp.route("/<int:record_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_record(record_id):
    """撤回审批（仅申请人可操作）"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)

    record = ApprovalRecord.query.get_or_404(record_id)
    if record.applicant_id != user_id:
        return error_response("只能撤回自己发起的审批", "400")
    if record.status != "pending":
        return error_response("当前状态不可撤回", "400")

    record.status = "cancelled"
    db.session.commit()
    return success_response(msg="已撤回")
