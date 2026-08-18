"""
Jenkins API 客户端
封装 Jenkins REST API 调用
"""
import requests
import logging
from app.config import Config

logger = logging.getLogger("sre-portal")


class JenkinsClient:
    """Jenkins API 客户端"""

    def __init__(self):
        self.url = Config.__dict__.get('JENKINS_URL', 'http://154.12.54.207:8082')
        self.username = Config.__dict__.get('JENKINS_USERNAME', 'admin')
        self.token = Config.__dict__.get('JENKINS_TOKEN', '')
        self.session = requests.Session()
        self.session.auth = (self.username, self.token)
        self.session.headers.update({'Content-Type': 'application/json'})

    def _request(self, method, path, **kwargs):
        """发送请求到 Jenkins"""
        url = f"{self.url}{path}"
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
            if resp.status_code == 200:
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
        return self._request('GET', f'/job/{job_name}/api/json')

    def get_builds(self, job_name, limit=20):
        """获取构建历史"""
        return self._request('GET', f'/job/{job_name}/api/json?tree=builds[number,status,duration,timestamp,url]{{0,{limit}}}')

    def get_build_detail(self, job_name, build_number):
        """获取构建详情"""
        return self._request('GET', f'/job/{job_name}/{build_number}/api/json')

    def get_build_log(self, job_name, build_number):
        """获取构建日志"""
        url = f"{self.url}/job/{job_name}/{build_number}/consoleText"
        try:
            resp = self.session.get(url, timeout=30)
            return {"log": resp.text}
        except Exception as e:
            return {"error": str(e)}

    def trigger_build(self, job_name, parameters=None):
        """触发构建"""
        if parameters:
            # 参数化构建
            params = {"token": "build"}
            params.update(parameters)
            return self._request('POST', f'/job/{job_name}/buildWithParameters', params=params)
        else:
            # 普通构建
            return self._request('POST', f'/job/{job_name}/build', params={"token": "build"})

    # ==================== 节点管理 ====================

    def get_nodes(self):
        """获取所有节点"""
        return self._request('GET', '/computer/api/json?tree=computer[displayName,displayName,offline,numExecutors,numExecutorsBusy]')

    def get_node_info(self, node_name):
        """获取节点详情"""
        return self._request('GET', f'/computer/{node_name}/api/json')

    # ==================== 队列管理 ====================

    def get_queue(self):
        """获取构建队列"""
        return self._request('GET', '/queue/api/json?tree=items[id,task[name,url],stuck,why,timestamp]')


# 全局客户端实例
jenkins_client = JenkinsClient()
