"""
Jenkins API 客户端
封装 Jenkins REST API 调用
"""
import requests
import logging
import base64
from urllib.parse import quote
from app.config import Config

logger = logging.getLogger("sre-portal")


class JenkinsClient:
    """Jenkins API 客户端"""

    def __init__(self):
        self.url = Config.__dict__.get('JENKINS_URL', 'http://154.12.54.207:8082')
        self.username = Config.__dict__.get('JENKINS_USERNAME', 'mubai')
        self.token = Config.__dict__.get('JENKINS_TOKEN', '')
        self.session = requests.Session()
        auth_str = f"{self.username}:{self.token}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {b64_auth}',
            'Content-Type': 'application/json'
        })

    def _request(self, method, path, **kwargs):
        """发送请求到 Jenkins"""
        url = f"{self.url}{path}"
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
            if 200 <= resp.status_code < 300:
                return resp.json() if resp.text else {}
            return {"error": f"HTTP {resp.status_code}", "message": resp.text}
        except Exception as e:
            logger.error(f"Jenkins API 请求失败: {e}")
            return {"error": str(e)}

    # ==================== 流水线管理 ====================

    def get_jobs(self):
        """获取所有流水线/任务"""
        return self._request('GET', '/api/json?tree=jobs[name,displayName,color,healthScore,lastBuild[number,status,timestamp]]')

    def get_job_info(self, job_name):
        """获取流水线详情"""
        return self._request('GET', f'/job/{quote(job_name, safe="")}/api/json')

    def get_job_config(self, job_name):
        """获取 Job 配置（XML），解析参数定义"""
        url = f"{self.url}/job/{quote(job_name, safe='')}/config.xml"
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 200:
                return {"xml": resp.text}
            return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def get_builds(self, job_name, limit=20):
        """获取构建历史"""
        return self._request('GET', f'/job/{quote(job_name, safe="")}/api/json?tree=builds[number,status,duration,timestamp,url]{{0,{limit}}}')

    def get_build_detail(self, job_name, build_number):
        """获取构建详情"""
        return self._request('GET', f'/job/{quote(job_name, safe="")}/{build_number}/api/json')

    def get_build_log(self, job_name, build_number):
        """获取构建日志"""
        url = f"{self.url}/job/{quote(job_name, safe='')}/{build_number}/consoleText"
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 200:
                return {"log": resp.text}
            return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def get_build_overview(self, job_name, build_number):
        """获取构建概览（stages 信息）"""
        # 使用 WfAPI (Pipeline REST API) 获取 stages
        stages_data = self._request('GET', f'/job/{quote(job_name, safe="")}/{build_number}/wfapi/describe')
        if "error" in stages_data:
            return stages_data

        # 解析 stages
        stages = stages_data.get("stages", [])
        result = {
            "name": stages_data.get("name", ""),
            "status": stages_data.get("status", ""),
            "startTimeMillis": stages_data.get("startTimeMillis", 0),
            "durationMillis": stages_data.get("durationMillis", 0),
            "stages": []
        }

        for stage in stages:
            result["stages"].append({
                "name": stage.get("name", ""),
                "status": stage.get("status", ""),
                "startTimeMillis": stage.get("startTimeMillis", 0),
                "durationMillis": stage.get("durationMillis", 0),
                "pauseDurationMillis": stage.get("pauseDurationMillis", 0),
            })

        return result

    def trigger_build(self, job_name, parameters=None):
        """触发构建"""
        encoded_name = quote(job_name, safe="")
        if parameters:
            # 参数化构建 - 通过 query string 传递参数
            params = {}
            for k, v in parameters.items():
                params[k] = str(v)
            return self._request('POST', f'/job/{encoded_name}/buildWithParameters', params=params)
        else:
            # 普通构建 - 不需要 token
            return self._request('POST', f'/job/{encoded_name}/build')

    # ==================== 节点管理 ====================

    def get_nodes(self):
        """获取所有节点"""
        return self._request('GET', '/computer/api/json?tree=computer[displayName,executors[currentExecutable[number]],offline,numExecutors,busyExecutors]')

    def get_node_info(self, node_name):
        """获取节点详情"""
        # Jenkins 内置节点的实际名称是 (master)
        if node_name in ("Built-In Node", "built-in-node", "master"):
            node_name = "(master)"
        encoded_name = quote(node_name, safe="")
        return self._request('GET', f'/computer/{encoded_name}/api/json')

    # ==================== 队列管理 ====================

    def get_queue(self):
        """获取构建队列"""
        return self._request('GET', '/queue/api/json?tree=items[id,task[name,url],stuck,why,timestamp]')


# 全局客户端实例
jenkins_client = JenkinsClient()
