import pymysql

conn = pymysql.connect(host='154.201.73.215', port=3306, user='root', password='Huanxin0321', database='sre_portal')
cur = conn.cursor()

# 1. 重命名表
print('=== 重命名表 ===')
renames = [
    ('todo_item', 'requirement'),
    ('todo_attachment', 'requirement_attachment'),
    ('todo_comment', 'requirement_comment'),
    ('todo_tag', 'requirement_label'),
    ('todo_item_tag', 'requirement_label_map'),
]
for old, new in renames:
    try:
        cur.execute(f'RENAME TABLE {old} TO {new}')
        print(f'  {old} -> {new} OK')
    except Exception as e:
        print(f'  {old} -> {new}: {e}')

# 2. 扩展 requirement 表
print()
print('=== 扩展 requirement 表 ===')
alters = [
    ('requirement_type', "VARCHAR(20) DEFAULT 'task' COMMENT '需求类型'"),
    ('reporter_id', 'INT COMMENT "提交人"'),
    ('assignee_id', 'INT COMMENT "负责人"'),
    ('milestone_id', 'BIGINT COMMENT "里程碑 ID"'),
    ('estimated_effort', 'VARCHAR(16) COMMENT "预估工作量"'),
    ('tags', 'JSON COMMENT "标签缓存"'),
    ('version', 'INT DEFAULT 1 COMMENT "版本号"'),
    ('approved_at', 'DATETIME COMMENT "审批通过时间"'),
    ('completed_at', 'DATETIME COMMENT "完成时间"'),
    ('deleted_at', 'DATETIME COMMENT "软删除时间"'),
]
for col, definition in alters:
    try:
        cur.execute(f'ALTER TABLE requirement ADD COLUMN {col} {definition}')
        print(f'  +{col} OK')
    except Exception as e:
        print(f'  +{col}: {e}')

try:
    cur.execute('ALTER TABLE requirement MODIFY COLUMN priority VARCHAR(4)')
    print('  priority VARCHAR(4) OK')
except Exception as e:
    print(f'  priority: {e}')

# 重命名列
print()
print('=== 重命名列 ===')
col_renames = [
    ('requirement_attachment', 'todo_id', 'requirement_id'),
    ('requirement_comment', 'todo_id', 'requirement_id'),
    ('requirement_label_map', 'todo_id', 'requirement_id'),
]
for table, old_col, new_col in col_renames:
    try:
        cur.execute(f'ALTER TABLE {table} CHANGE COLUMN {old_col} {new_col} INT')
        print(f'  {table}.{old_col} -> {new_col} OK')
    except Exception as e:
        print(f'  {table}.{old_col}: {e}')

# 3. 创建 milestone 表
print()
print('=== 创建 milestone 表 ===')
cur.execute("""
CREATE TABLE IF NOT EXISTS milestone (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id INT COMMENT '关联项目 ID',
    title VARCHAR(128) NOT NULL COMMENT '里程碑标题',
    description TEXT COMMENT '描述',
    due_date DATE COMMENT '截止日期',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_milestone_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  milestone OK')

# 4. 创建审批流表
print()
print('=== 创建审批流表 ===')
cur.execute("""
CREATE TABLE IF NOT EXISTS approval_template (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id INT COMMENT '关联项目 NULL=全局',
    name VARCHAR(128) NOT NULL COMMENT '模板名称',
    description TEXT COMMENT '描述',
    trigger_conditions JSON COMMENT '触发条件',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  approval_template OK')

cur.execute("""
CREATE TABLE IF NOT EXISTS approval_template_node (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    template_id BIGINT COMMENT '关联模板',
    step_number INT NOT NULL COMMENT '步骤序号',
    approver_type VARCHAR(20) NOT NULL COMMENT '审批人类型',
    approver_id VARCHAR(128) COMMENT '审批人 ID',
    approval_mode VARCHAR(10) DEFAULT 'all' COMMENT '审批模式',
    timeout_hours INT COMMENT '超时小时数',
    escalate_to_id VARCHAR(128) COMMENT '升级目标',
    INDEX idx_approval_node_template (template_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  approval_template_node OK')

cur.execute("""
CREATE TABLE IF NOT EXISTS approval_instance (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    requirement_id INT COMMENT '关联需求',
    template_id BIGINT COMMENT '使用模板',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态',
    current_step INT DEFAULT 1 COMMENT '当前步骤',
    initiated_by INT COMMENT '发起人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME COMMENT '完成时间',
    INDEX idx_approval_instance_req (requirement_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  approval_instance OK')

cur.execute("""
CREATE TABLE IF NOT EXISTS approval_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    instance_id BIGINT COMMENT '关联实例',
    step_number INT NOT NULL COMMENT '步骤序号',
    approver_id INT COMMENT '审批人',
    action VARCHAR(20) NOT NULL COMMENT '操作',
    comment TEXT COMMENT '审批意见',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_approval_record_instance (instance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  approval_record OK')

# 5. 创建版本历史和活动日志表
print()
print('=== 创建版本历史和活动日志表 ===')
cur.execute("""
CREATE TABLE IF NOT EXISTS requirement_version (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    requirement_id INT COMMENT '关联需求',
    version_number INT NOT NULL COMMENT '版本号',
    snapshot JSON COMMENT '完整快照',
    changed_fields JSON COMMENT '变更字段列表',
    changed_by INT COMMENT '变更人',
    change_type VARCHAR(32) COMMENT '变更类型',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_req_version_req (requirement_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  requirement_version OK')

cur.execute("""
CREATE TABLE IF NOT EXISTS requirement_activity (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    requirement_id INT COMMENT '关联需求',
    user_id INT COMMENT '操作人',
    action VARCHAR(64) NOT NULL COMMENT '操作类型',
    field_name VARCHAR(64) COMMENT '变更字段',
    old_value TEXT COMMENT '旧值',
    new_value TEXT COMMENT '新值',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_req_activity_req (requirement_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print('  requirement_activity OK')

# 6. 数据迁移
print()
print('=== 数据迁移 ===')
cur.execute("UPDATE requirement SET status = 'proposed' WHERE status = 'pending'")
cur.execute("UPDATE requirement SET status = 'done' WHERE status = 'completed'")
cur.execute("UPDATE requirement SET status = 'rejected' WHERE status = 'cancelled'")
print('  状态映射 OK')

cur.execute("UPDATE requirement SET priority = 'P3' WHERE priority = 'low'")
cur.execute("UPDATE requirement SET priority = 'P2' WHERE priority = 'medium'")
cur.execute("UPDATE requirement SET priority = 'P1' WHERE priority = 'high'")
cur.execute("UPDATE requirement SET priority = 'P0' WHERE priority = 'urgent'")
print('  优先级映射 OK')

cur.execute("UPDATE requirement SET requirement_type = 'task'")
print('  需求类型默认值 OK')

conn.commit()

# 验证
print()
print('=== 验证 ===')
cur.execute('SHOW TABLES LIKE "requirement%"')
print(f'  requirement 相关表: {[r[0] for r in cur.fetchall()]}')
cur.execute('SHOW TABLES LIKE "approval%"')
print(f'  approval 相关表: {[r[0] for r in cur.fetchall()]}')
cur.execute('SHOW TABLES LIKE "milestone"')
print(f'  milestone 表: {[r[0] for r in cur.fetchall()]}')
cur.execute('SELECT COUNT(*) FROM requirement')
print(f'  requirement 记录数: {cur.fetchone()[0]}')

cur.close()
conn.close()
print()
print('数据库迁移完成!')
