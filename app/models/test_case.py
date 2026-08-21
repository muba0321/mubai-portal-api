"""
测试管理模型
"""
from datetime import datetime

from app.extensions import db


class TestCase(db.Model):
    """测试用例"""
    __tablename__ = "test_case"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, comment="关联项目")
    title = db.Column(db.String(256), nullable=False, comment="用例标题")
    description = db.Column(db.Text, comment="用例描述")
    test_type = db.Column(db.String(20), nullable=False, default="manual", comment="类型：api / manual")
    priority = db.Column(db.String(4), default="P2", comment="优先级：P0/P1/P2/P3")
    status = db.Column(db.String(32), default="draft", comment="状态：draft / active / archived")
    tags = db.Column(db.JSON, comment="标签")

    # API 测试配置
    api_method = db.Column(db.String(10), comment="HTTP 方法")
    api_url = db.Column(db.String(512), comment="接口 URL")
    api_headers = db.Column(db.JSON, comment="请求头")
    api_body = db.Column(db.Text, comment="请求体")
    api_expected_status = db.Column(db.Integer, comment="期望状态码")
    api_expected_body = db.Column(db.Text, comment="期望响应体")

    # 手工测试配置
    manual_steps = db.Column(db.JSON, comment="手工测试步骤")
    preconditions = db.Column(db.Text, comment="前置条件")

    # 通用字段
    created_by = db.Column(db.String(64), comment="创建人")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 关系
    project = db.relationship("Project", backref="test_cases")
    requirements = db.relationship("Requirement", secondary="test_case_requirement", backref="test_cases")

    def __repr__(self):
        return f"<TestCase {self.title}>"


class TestCaseRequirementMap(db.Model):
    """测试用例与需求关联表"""
    __tablename__ = "test_case_requirement"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_case_id = db.Column(db.Integer, db.ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False)
    requirement_id = db.Column(db.Integer, db.ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class TestExecution(db.Model):
    """测试执行记录"""
    __tablename__ = "test_execution"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_case_id = db.Column(db.Integer, db.ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False)
    executor = db.Column(db.String(64), comment="执行人")
    result = db.Column(db.String(20), comment="结果：pass / fail / blocked / skipped")
    actual_response = db.Column(db.Text, comment="实际响应")
    notes = db.Column(db.Text, comment="备注")
    environment = db.Column(db.String(64), comment="测试环境")
    executed_at = db.Column(db.DateTime, default=datetime.now)
    duration_ms = db.Column(db.Integer, comment="执行耗时（毫秒）")

    # 关系
    test_case = db.relationship("TestCase", backref="executions")
    steps = db.relationship("TestExecutionStep", backref="execution", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TestExecution {self.id}>"


class TestExecutionStep(db.Model):
    """手工测试步骤结果"""
    __tablename__ = "test_execution_step"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    execution_id = db.Column(db.Integer, db.ForeignKey("test_execution.id", ondelete="CASCADE"), nullable=False)
    step_index = db.Column(db.Integer, nullable=False, comment="步骤序号")
    status = db.Column(db.String(20), comment="步骤结果：pass / fail / skip")
    actual_result = db.Column(db.Text, comment="实际结果")
    notes = db.Column(db.Text, comment="备注")

    def __repr__(self):
        return f"<TestExecutionStep {self.step_index}>"
