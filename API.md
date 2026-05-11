# SRE Portal API 接口文档

> 基础地址：`http://localhost:5000`
> 所有接口统一前缀：`/api/v1/`（前端通过 `/dev-api` 代理，实际到达后端时已去除前缀）

---

## 统一规范

### 统一响应格式

```json
{
  "code": "00000",
  "data": {},
  "msg": "一切ok"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | `"00000"` 表示成功，其他为错误码 |
| `data` | any | 响应数据体（类型随接口变化） |
| `msg` | string | 提示信息 |

### 鉴权方式

除登录接口外，所有接口需要在请求头携带 Token：

```
Authorization: Bearer {access_token}
```

### 分页格式

**请求参数**：
- `pageNum` (int) — 页码，从 1 开始
- `pageSize` (int) — 每页条数

**响应格式**（在 `data` 中）：
```json
{
  "list": [],
  "total": 100
}
```

### 下拉选项格式

```json
{ "label": "显示名称", "value": "实际值" }
```

### 错误码

| 错误码 | 含义 |
|---|---|
| `00000` | 成功 |
| `A0230` | 访问令牌无效或过期 |
| `A0231` | 刷新令牌无效 |
| `A0300` | 用户名或密码错误 |
| `A0301` | 权限不足 |
| `40400` | 资源不存在 |
| `50000` | 系统内部错误 |

### 字段命名规范

- 数据库字段：`snake_case`（如 `external_ip`）
- API 响应字段：`camelCase`（如 `externalIp`）
- API 请求字段：`camelCase`

---

## 1. 认证模块 `/api/v1/auth`

### 1.1 登录

```
POST /api/v1/auth/login
```

**请求体**：

```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应**：

```json
{
  "code": "00000",
  "data": {
    "accessToken": "eyJhbGci...",
    "refreshToken": "eyJhbGci..."
  },
  "msg": "登录成功"
}
```

### 1.2 刷新 Token

```
POST /api/v1/auth/refresh-token?refresh_token={refresh_token}
```

**响应**：

```json
{
  "code": "00000",
  "data": {
    "accessToken": "eyJhbGci..."
  },
  "msg": "一切ok"
}
```

### 1.3 退出登录

```
POST /api/v1/auth/logout
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": null,
  "msg": "退出成功"
}
```

---

## 2. CMDB 虚拟机管理 `/api/v1/cmdb`

### VM 对象结构

```json
{
  "id": 1,
  "name": "vm-web-01",
  "cluster": "OpenClaw-Main",
  "externalIp": "38.246.245.32",
  "internalIp": "10.0.118.4",
  "description": "OpenClaw 主节点",
  "status": 1,
  "tenant": "OpenClaw",
  "vcpus": 4,
  "memory": 8192,
  "disk": "100GB",
  "accessUrl": "portal.mubai.top",
  "createdAt": "2026-05-11 16:07:45",
  "updatedAt": "2026-05-11 16:07:45"
}
```

### 2.1 分页查询虚拟机列表

```
GET /api/v1/cmdb/vms?pageNum=1&pageSize=10&keywords=&cluster=&status=&tenant=
```

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pageNum` | int | 是 | 页码，从 1 开始 |
| `pageSize` | int | 是 | 每页条数 |
| `keywords` | string | 否 | 关键词搜索（匹配 name, cluster, description, externalIp, internalIp） |
| `cluster` | string | 否 | 集群筛选 |
| `status` | int | 否 | 状态筛选（1=在线, 0=离线） |
| `tenant` | string | 否 | 租户筛选 |

**响应**：

```json
{
  "code": "00000",
  "data": {
    "list": [
      {
        "id": 1,
        "name": "vm-web-01",
        "cluster": "OpenClaw-Main",
        "externalIp": "38.246.245.32",
        "internalIp": "10.0.118.4",
        "description": "OpenClaw 主节点",
        "status": 1,
        "tenant": "OpenClaw",
        "vcpus": 4,
        "memory": 8192,
        "disk": "100GB",
        "accessUrl": "portal.mubai.top",
        "createdAt": "2026-05-11 16:07:45",
        "updatedAt": "2026-05-11 16:07:45"
      }
    ],
    "total": 12
  },
  "msg": "一切ok"
}
```

### 2.2 获取 VM 详情

```
GET /api/v1/cmdb/vms/:id
```

**响应**：返回单个 VM 对象。

### 2.3 新增虚拟机

```
POST /api/v1/cmdb/vms
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体**：

```json
{
  "name": "vm-web-02",
  "cluster": "OpenClaw-Main",
  "externalIp": "38.246.245.35",
  "internalIp": "10.0.118.7",
  "description": "OpenClaw 从节点",
  "status": 1,
  "tenant": "OpenClaw",
  "vcpus": 8,
  "memory": 16384,
  "disk": "200GB",
  "accessUrl": ""
}
```

**必填字段**：`name`, `cluster`, `externalIp`, `internalIp`, `tenant`

**响应**：

```json
{
  "code": "00000",
  "data": null,
  "msg": "新增成功"
}
```

### 2.4 编辑虚拟机

```
PUT /api/v1/cmdb/vms/:id
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体**：同新增。

**响应**：

```json
{
  "code": "00000",
  "data": null,
  "msg": "修改成功"
}
```

### 2.5 删除虚拟机

```
DELETE /api/v1/cmdb/vms/:id
Authorization: Bearer {token}
```

**说明**：逻辑删除（设置 `deleted=1`）。

**响应**：

```json
{
  "code": "00000",
  "data": null,
  "msg": "删除成功"
}
```

### 2.6 批量删除

```
DELETE /api/v1/cmdb/vms/batch
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体**：

```json
{
  "ids": [1, 2, 3]
}
```

**响应**：

```json
{
  "code": "00000",
  "data": null,
  "msg": "批量删除成功"
}
```

### 2.7 导入虚拟机（Excel/CSV）

```
POST /api/v1/cmdb/vms/import
Authorization: Bearer {token}
Content-Type: multipart/form-data
```

**参数**：`file` — Excel 或 CSV 文件

**CSV/Excel 列顺序**：名称, 集群, 外部IP, 内部IP, 租户, VCPUS, 内存(MB), 硬盘, 访问URL

**响应**：

```json
{
  "code": "00000",
  "data": {
    "successCount": 10,
    "failCount": 2,
    "errors": ["第3行：名称 'vm-03' 已存在"]
  },
  "msg": "导入完成"
}
```

### 2.8 导出虚拟机（Excel）

```
GET /api/v1/cmdb/vms/export?keywords=&cluster=&status=&tenant=
Authorization: Bearer {token}
```

**Query 参数**：同列表查询条件。

**响应**：Excel 文件流 (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)

### 2.9 集群选项列表

```
GET /api/v1/cmdb/clusters
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": [
    { "label": "Dev-Cluster", "value": "Dev-Cluster" },
    { "label": "Infra-Cluster", "value": "Infra-Cluster" },
    { "label": "K8s-Production", "value": "K8s-Production" },
    { "label": "OpenClaw-Main", "value": "OpenClaw-Main" }
  ],
  "msg": "一切ok"
}
```

### 2.10 租户选项列表

```
GET /api/v1/cmdb/tenants
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": [
    { "label": "Monitoring", "value": "Monitoring" },
    { "label": "OpenClaw", "value": "OpenClaw" },
    { "label": "Platform", "value": "Platform" }
  ],
  "msg": "一切ok"
}
```

---

## 3. Dashboard 首页 `/api/v1/dashboard`

### 3.1 获取系统状态

```
GET /api/v1/dashboard/system-status
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": {
    "serverOnline": 24,
    "serviceRunning": 142,
    "networkStatus": "normal",
    "storageUsage": "78%",
    "alertPending": 3,
    "cpuLoad": "45%",
    "lastUpdated": "2026-05-11 16:07:45"
  },
  "msg": "一切ok"
}
```

### 3.2 获取常用链接

```
GET /api/v1/dashboard/common-links
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": [
    {
      "id": 1,
      "title": "CMDB 虚拟机列表",
      "description": "管理所有虚拟机资产",
      "url": "/cmdb",
      "icon": "Document",
      "sort": 1
    },
    {
      "id": 2,
      "title": "性能监控大盘",
      "description": "实时查看系统性能指标",
      "url": "/monitor",
      "icon": "TrendCharts",
      "sort": 2
    }
  ],
  "msg": "一切ok"
}
```

### 3.3 获取最近访问记录

```
GET /api/v1/dashboard/recent-visits
Authorization: Bearer {token}
```

**说明**：返回当前用户的最近访问记录，按时间倒序，最多 4 条。

**响应**：

```json
{
  "code": "00000",
  "data": [
    {
      "pagePath": "/cmdb",
      "pageTitle": "CMDB 虚拟机管理",
      "visitedAt": "2026-05-11 16:32:25"
    }
  ],
  "msg": "一切ok"
}
```

### 3.4 记录最近访问

```
POST /api/v1/dashboard/recent-visits
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体**：

```json
{
  "pagePath": "/cmdb",
  "pageTitle": "CMDB 虚拟机管理"
}
```

**说明**：同一路径会更新访问时间而非插入新记录。

**响应**：

```json
{
  "code": "00000",
  "data": null,
  "msg": "一切ok"
}
```

---

## 4. 系统接口 `/api/v1`

### 4.1 获取当前用户信息

```
GET /api/v1/users/me
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": {
    "userId": 1,
    "username": "admin",
    "email": "admin@sre.com",
    "role": "admin"
  },
  "msg": "一切ok"
}
```

### 4.2 获取动态路由/菜单

```
GET /api/v1/menus/routes
Authorization: Bearer {token}
```

**响应**：

```json
{
  "code": "00000",
  "data": [
    {
      "path": "/dashboard",
      "component": "Layout",
      "redirect": "/dashboard",
      "meta": { "title": "首页", "icon": "HomeFilled" },
      "children": [
        { "path": "dashboard", "component": "dashboard/index", "meta": { "title": "首页", "icon": "HomeFilled" } }
      ]
    },
    {
      "path": "/cmdb",
      "component": "Layout",
      "redirect": "/cmdb",
      "meta": { "title": "CMDB 管理", "icon": "Monitor" },
      "children": [
        { "path": "cmdb", "component": "cmdb/index", "meta": { "title": "虚拟机管理", "icon": "Monitor" } }
      ]
    }
  ],
  "msg": "一切ok"
}
```

---

## 5. 测试账号

| 用户名 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | admin |

## 6. 环境配置

| 项目 | 值 |
|---|---|
| 后端地址 | `http://localhost:5000` |
| 前端代理前缀 | `/dev-api`（Vite 自动转发） |
| 数据库 | MySQL 8.0 @ `154.12.54.207:3306` |
| 数据库名 | `sre_portal` |
| Python | 3.14+ |
| 依赖安装 | `pip install -r requirements.txt` |
| 启动命令 | `python run.py` |
