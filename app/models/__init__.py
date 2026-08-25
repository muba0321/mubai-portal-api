from app.models.cmdb_vm import CmdbVM
from app.models.sys import SysMonitor, SysCommonLink, SysRecentVisit
from app.models.sys_user import SysUser
from app.models.setting import SysSetting
from app.models.requirement import Project, Requirement, Milestone, RequirementCommit
from app.models.requirement_extend import (
    RequirementAttachment, RequirementComment, RequirementLabel, RequirementLabelMap,
    RequirementVersion, RequirementActivity,
    ReqApprovalTemplate, ReqApprovalTemplateNode, ReqApprovalInstance, ReqApprovalRecord,
)
from app.models.credential import Credential
from app.models.alerting import AlertMetric, AlertRule, NotificationChannel, AlertTemplate
# RBAC models
from app.models.dept import Dept
from app.models.sys_role import Role
from app.models.sys_user_role import UserRole
from app.models.sys_menu import Menu
from app.models.sys_role_menu import RoleMenu
from app.models.sys_oper_log import OperLog
from app.models.approval import ApprovalTemplate, ApprovalRecord, ApprovalStep
from app.models.grafana_ai_history import GrafanaAiHistory
from app.models.ansible_job import AnsibleJob, AnsibleSchedule, AnsibleCommand, AnsibleScheduleLog
from app.models.service_backup import ServiceBackup, ServiceBackupLog
# 测试管理
from app.models.test_case import TestCase, TestCaseRequirementMap, TestExecution, TestExecutionStep
# 知识库管理
from app.models.knowledge_base import KbFile, KbSyncLog
# CICD 流程管理
from app.models.cicd import CICDStageConfig, CICDMilestone
