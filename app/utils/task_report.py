"""
定时任务报告数据结构
提供统一的结构化输出格式，用于三个内置任务：
- CMDB 自动巡检
- 磁盘使用检查
- 服务健康检查
"""
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Issue:
    """发现的问题"""
    host: str
    level: str          # info / warning / critical
    title: str
    expected: str
    actual: str
    impact: str
    suggestion: str


@dataclass
class TaskReport:
    """任务执行报告"""
    task_name: str
    task_type: str
    total_hosts: int = 0
    summary: dict = field(default_factory=dict)
    details: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    raw_output: str = ""

    def to_dict(self) -> dict:
        return {
            "task_name": self.task_name,
            "task_type": self.task_type,
            "total_hosts": self.total_hosts,
            "summary": self.summary,
            "details": self.details,
            "issues": [
                {
                    "host": i.host, "level": i.level, "title": i.title,
                    "expected": i.expected, "actual": i.actual,
                    "impact": i.impact, "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "raw_output": self.raw_output,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
