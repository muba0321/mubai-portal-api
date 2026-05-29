from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.utils.response import success, error
from app.models.alerting import AlertMetric, AlertRule, NotificationChannel, AlertTemplate
from app.extensions import db
from datetime import datetime

alerting_bp = Blueprint("alerting", __name__)


# ============ Manual Serialization ============

def metric_to_dict(m):
    return {
        "id": m.id,
        "name": m.name,
        "display_name": m.display_name,
        "group": m.group,
        "description": m.description,
        "promql": m.promql,
        "unit": m.unit,
        "source_type": m.source_type,
        "enabled": m.enabled,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def rule_to_dict(r):
    d = {
        "id": r.id,
        "name": r.name,
        "metric_id": r.metric_id,
        "condition_operator": r.condition_operator,
        "condition_value": r.condition_value,
        "condition_duration": r.condition_duration,
        "severity": r.severity,
        "notification_channels": r.notification_channels,
        "source_type": r.source_type,
        "template_id": r.template_id,
        "enabled": r.enabled,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
    if r.metric:
        d["metric"] = metric_to_dict(r.metric)
    return d


def channel_to_dict(c):
    return {
        "id": c.id,
        "type": c.type,
        "name": c.name,
        "webhook_url": c.webhook_url,
        "email_recipients": c.email_recipients,
        "message_template": c.message_template,
        "level_filter": c.level_filter,
        "silence_period": c.silence_period,
        "enabled": c.enabled,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def template_to_dict(t):
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "group": t.group,
        "source_type": t.source_type,
        "metric_count": t.metric_count,
        "rule_count": t.rule_count,
        "metrics_def": t.metrics_def,
        "rules_def": t.rules_def,
        "enabled": t.enabled,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ============ Alert Metrics ============

@alerting_bp.route("/metrics", methods=["GET"])
@jwt_required()
def list_metrics():
    group = request.args.get("group")
    source_type = request.args.get("source_type")
    query = AlertMetric.query
    if group:
        query = query.filter_by(group=group)
    if source_type:
        query = query.filter_by(source_type=source_type)
    metrics = query.order_by(AlertMetric.group, AlertMetric.name).all()
    return success(data=[metric_to_dict(m) for m in metrics])


@alerting_bp.route("/metrics", methods=["POST"])
@jwt_required()
def create_metric():
    data = request.get_json()
    metric = AlertMetric(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        group=data.get("group", "custom"),
        description=data.get("description", ""),
        promql=data.get("promql", ""),
        unit=data.get("unit", ""),
        source_type=data.get("source_type", "custom"),
    )
    db.session.add(metric)
    db.session.commit()
    return jsonify(metric_to_dict(metric)), 201


@alerting_bp.route("/metrics/<int:metric_id>", methods=["GET"])
@jwt_required()
def get_metric(metric_id):
    metric = AlertMetric.query.get_or_404(metric_id)
    return jsonify(metric_to_dict(metric))


@alerting_bp.route("/metrics/<int:metric_id>", methods=["PUT"])
@jwt_required()
def update_metric(metric_id):
    metric = AlertMetric.query.get_or_404(metric_id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(metric, key):
            setattr(metric, key, value)
    metric.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(metric_to_dict(metric))


@alerting_bp.route("/metrics/<int:metric_id>", methods=["DELETE"])
@jwt_required()
def delete_metric(metric_id):
    metric = AlertMetric.query.get_or_404(metric_id)
    db.session.delete(metric)
    db.session.commit()
    return jsonify({"message": "删除成功"})


# ============ Alert Rules ============

@alerting_bp.route("/rules", methods=["GET"])
@jwt_required()
def list_rules():
    severity = request.args.get("severity")
    source_type = request.args.get("source_type")
    enabled = request.args.get("enabled")
    query = AlertRule.query
    if severity:
        query = query.filter_by(severity=severity)
    if source_type:
        query = query.filter_by(source_type=source_type)
    if enabled is not None:
        query = query.filter_by(enabled=enabled.lower() == "true")
    rules = query.order_by(AlertRule.severity, AlertRule.name).all()
    return success(data=[rule_to_dict(r) for r in rules])


@alerting_bp.route("/rules", methods=["POST"])
@jwt_required()
def create_rule():
    data = request.get_json()
    rule = AlertRule(
        name=data["name"],
        metric_id=data.get("metric_id"),
        condition_operator=data.get("condition_operator", ">"),
        condition_value=data.get("condition_value", 0),
        condition_duration=data.get("condition_duration", 60),
        severity=data.get("severity", "P2"),
        notification_channels=data.get("notification_channels"),
        source_type=data.get("source_type", "custom"),
        template_id=data.get("template_id"),
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule_to_dict(rule)), 201


@alerting_bp.route("/rules/<int:rule_id>", methods=["GET"])
@jwt_required()
def get_rule(rule_id):
    rule = AlertRule.query.get_or_404(rule_id)
    return jsonify(rule_to_dict(rule))


@alerting_bp.route("/rules/<int:rule_id>", methods=["PUT"])
@jwt_required()
def update_rule(rule_id):
    rule = AlertRule.query.get_or_404(rule_id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(rule_to_dict(rule))


@alerting_bp.route("/rules/<int:rule_id>", methods=["DELETE"])
@jwt_required()
def delete_rule(rule_id):
    rule = AlertRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    return jsonify({"message": "删除成功"})


@alerting_bp.route("/rules/<int:rule_id>/toggle", methods=["PUT"])
@jwt_required()
def toggle_rule(rule_id):
    rule = AlertRule.query.get_or_404(rule_id)
    rule.enabled = not rule.enabled
    rule.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(rule_to_dict(rule))


# ============ Notification Channels ============

@alerting_bp.route("/channels", methods=["GET"])
@jwt_required()
def list_channels():
    channel_type = request.args.get("type")
    query = NotificationChannel.query
    if channel_type:
        query = query.filter_by(type=channel_type)
    channels = query.order_by(NotificationChannel.type, NotificationChannel.name).all()
    return success(data=[channel_to_dict(c) for c in channels])


@alerting_bp.route("/channels", methods=["POST"])
@jwt_required()
def create_channel():
    data = request.get_json()
    channel = NotificationChannel(
        type=data["type"],
        name=data["name"],
        webhook_url=data.get("webhook_url"),
        email_recipients=data.get("email_recipients"),
        message_template=data.get("message_template"),
        level_filter=data.get("level_filter", "all"),
        silence_period=data.get("silence_period", 300),
    )
    db.session.add(channel)
    db.session.commit()
    return jsonify(channel_to_dict(channel)), 201


@alerting_bp.route("/channels/<int:channel_id>", methods=["GET"])
@jwt_required()
def get_channel(channel_id):
    channel = NotificationChannel.query.get_or_404(channel_id)
    return jsonify(channel_to_dict(channel))


@alerting_bp.route("/channels/<int:channel_id>", methods=["PUT"])
@jwt_required()
def update_channel(channel_id):
    channel = NotificationChannel.query.get_or_404(channel_id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(channel, key):
            setattr(channel, key, value)
    channel.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(channel_to_dict(channel))


@alerting_bp.route("/channels/<int:channel_id>", methods=["DELETE"])
@jwt_required()
def delete_channel(channel_id):
    channel = NotificationChannel.query.get_or_404(channel_id)
    db.session.delete(channel)
    db.session.commit()
    return jsonify({"message": "删除成功"})


# ============ Alert Templates ============

@alerting_bp.route("/templates", methods=["GET"])
@jwt_required()
def list_templates():
    import json
    group = request.args.get("group")
    source_type = request.args.get("source_type")
    query = AlertTemplate.query
    if group:
        query = query.filter_by(group=group)
    if source_type:
        query = query.filter_by(source_type=source_type)
    templates = query.order_by(AlertTemplate.group, AlertTemplate.name).all()
    return success(data=[template_to_dict(t) for t in templates])


@alerting_bp.route("/templates", methods=["POST"])
@jwt_required()
def create_template():
    import json
    data = request.get_json()
    template = AlertTemplate(
        name=data["name"],
        description=data.get("description", ""),
        group=data.get("group", "custom"),
        source_type=data.get("source_type", "custom"),
        metric_count=data.get("metric_count", 0),
        rule_count=data.get("rule_count", 0),
        metrics_def=json.dumps(data.get("metrics", [])),
        rules_def=json.dumps(data.get("rules", [])),
    )
    db.session.add(template)
    db.session.commit()
    return jsonify(template_to_dict(template)), 201


@alerting_bp.route("/templates/<int:template_id>", methods=["GET"])
@jwt_required()
def get_template(template_id):
    import json
    template = AlertTemplate.query.get_or_404(template_id)
    result = template_to_dict(template)
    if template.metrics_def:
        result["metrics"] = json.loads(template.metrics_def)
    if template.rules_def:
        result["rules"] = json.loads(template.rules_def)
    return jsonify(result)


@alerting_bp.route("/templates/<int:template_id>/apply", methods=["POST"])
@jwt_required()
def apply_template(template_id):
    """一键应用模板：将模板中的指标和规则批量创建到数据库中"""
    import json
    template = AlertTemplate.query.get_or_404(template_id)

    metrics = json.loads(template.metrics_def) if template.metrics_def else []
    rules = json.loads(template.rules_def) if template.rules_def else []

    created_metrics = []
    created_rules = []

    # Create metrics from template
    for m in metrics:
        existing = AlertMetric.query.filter_by(name=m["name"]).first()
        if existing:
            created_metrics.append({"id": existing.id, "name": m["name"], "status": "exists"})
        else:
            metric = AlertMetric(
                name=m["name"],
                display_name=m.get("display_name", m["name"]),
                group=m.get("group", template.group),
                description=m.get("description", ""),
                promql=m.get("promql", ""),
                unit=m.get("unit", ""),
                source_type="builtin",
            )
            db.session.add(metric)
            db.session.flush()
            created_metrics.append({"id": metric.id, "name": m["name"], "status": "created"})

    # Create rules from template
    for r in rules:
        metric = AlertMetric.query.filter_by(name=r.get("metric_name")).first()
        metric_id = metric.id if metric else None

        rule = AlertRule(
            name=r["name"],
            metric_id=metric_id,
            condition_operator=r.get("condition_operator", ">"),
            condition_value=r.get("condition_value", 0),
            condition_duration=r.get("condition_duration", 60),
            severity=r.get("severity", "P2"),
            notification_channels=r.get("notification_channels"),
            source_type="builtin",
            template_id=template.id,
        )
        db.session.add(rule)
        created_rules.append({"name": r["name"], "status": "created"})

    db.session.commit()
    created_count = len([m for m in created_metrics if m["status"] == "created"])
    return jsonify({
        "message": f"应用成功：创建 {created_count} 个指标，{len(created_rules)} 条规则",
        "metrics": created_metrics,
        "rules": created_rules,
    })


@alerting_bp.route("/templates/<int:template_id>", methods=["PUT"])
@jwt_required()
def update_template(template_id):
    import json
    template = AlertTemplate.query.get_or_404(template_id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(template, key):
            setattr(template, key, value)
    if "metrics" in data:
        template.metrics_def = json.dumps(data["metrics"])
    if "rules" in data:
        template.rules_def = json.dumps(data["rules"])
    template.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(template_to_dict(template))


@alerting_bp.route("/templates/<int:template_id>", methods=["DELETE"])
@jwt_required()
def delete_template(template_id):
    template = AlertTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    return jsonify({"message": "删除成功"})


# ============ Statistics ============

@alerting_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_stats():
    metrics_count = AlertMetric.query.filter_by(enabled=True).count()
    templates_count = AlertTemplate.query.filter_by(enabled=True, source_type="builtin").count()
    rules_count = AlertRule.query.count()
    active_rules = AlertRule.query.filter_by(enabled=True).count()
    channels_count = NotificationChannel.query.filter_by(enabled=True).count()
    return success(data={
        "metrics_count": metrics_count,
        "templates_count": templates_count,
        "rules_count": rules_count,
        "active_rules": active_rules,
        "channels_count": channels_count,
    })
