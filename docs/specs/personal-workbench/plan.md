# 个人工作台 V1 技术设计方案 (Plan)

- **版本**: V1.0 (总控驾驶舱首期)
- **目标设备**: 电脑全屏 (Desktop) + 手机端移动自适应 (Mobile Responsive)
- **技术栈**: 原生极简技术栈（Python 3.9 + SQLite 3 + 原生 HTML5 / CSS3 / ES6）
- **特点**: 零构建依赖、离线秒开、支持后续外网直连访问（Tailscale/公网代理）

---

## 一、系统架构与数据模型设计 (Data Models)

### 1. SQLite 数据表演进方案 (`workbench.db`)

```sql
-- 1. 任务表 (扩展支持软删除、排序与编辑)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'task',
    status TEXT DEFAULT 'pending',        -- 'pending', 'done'
    priority TEXT DEFAULT 'normal',       -- 'top3', 'high', 'normal'
    project_id TEXT,
    due_date TEXT,
    is_deleted INTEGER DEFAULT 0,         -- 软删除标记: 0正常, 1已删除进回收站
    deleted_at TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT,
    completed_at TEXT
);

-- 2. 阶段项目表 (扩展支持里程碑与复盘)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,                 -- 'active', 'hold', 'done'
    status_text TEXT,
    progress INTEGER DEFAULT 0,
    summary TEXT,
    decision TEXT,
    next_step TEXT,
    milestones_json TEXT DEFAULT '[]',    -- 阶段里程碑节点
    retros_json TEXT DEFAULT '{}',        -- 完结复盘总结
    artifacts_json TEXT DEFAULT '[]',
    updated_at TEXT
);

-- 3. 持续化/自动化守护任务表 (头条、百家号、后台监控)
CREATE TABLE IF NOT EXISTS continuous_tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    platform TEXT,                        -- 'toutiao', 'baijiahao', 'general'
    status TEXT DEFAULT 'idle',           -- 'active', 'running', 'idle', 'error'
    progress INTEGER DEFAULT 0,           -- 实时任务进度 0-100%
    streak_days INTEGER DEFAULT 0,        -- 连续平稳运行天数
    last_run_at TEXT,
    logs_json TEXT DEFAULT '[]',          -- 最新日志滚动流 (按时间戳倒序)
    created_at TEXT
);

-- 4. 撤销与审计日志表 (支持 5s 撤销与回收站还原)
CREATE TABLE IF NOT EXISTS action_audit_logs (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,            -- 'toggle', 'delete', 'update', 'restore'
    entity_type TEXT NOT NULL,            -- 'task', 'project', 'continuous'
    entity_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT
);
```

---

## 二、RESTful API 接口扩展清单 (`workbench_server.py`)

* `GET /api/v1/state`：全盘大屏数据聚合（任务、昨日战报、项目沙盘、持续化守护任务、统计指标、回收站数量）
* `POST /api/v1/tasks/create`：快速创建待办
* `POST /api/v1/tasks/update`：原地编辑任务标题、优先级、所属项目
* `POST /api/v1/tasks/toggle`：打勾完成/取消完成（写入审计与撤销栈）
* `POST /api/v1/tasks/delete`：软删除（移入回收站）
* `POST /api/v1/tasks/restore`：从回收站恢复任务
* `POST /api/v1/tasks/undo`：5 秒撤销上一步操作
* `POST /api/v1/projects/update`：更新项目进度、唯一步伐 Next Action
* `POST /api/v1/continuous/ping`：自动化脚本上报进度与日志（供头条/百家号定时任务写入）
* `GET /api/v1/recycle_bin`：查看已删除任务

---

## 三、前端视觉与交互设计 (`dashboard.html`)

### 1. 视觉语言 (对标大闸蟹科技指挥大屏)
* **配色方案**：深海蓝黑底 `#080c16`，霓虹青 `#06b6d4`、电光蓝 `#3b82f6`、警示金 `#f59e0b`、荧光绿 `#10b981`、珊瑚红 `#ef4444`。
* **卡片质感**：半透明毛玻璃 (`backdrop-filter: blur(10px)`)、微光边框 (`border: 1px solid rgba(59, 130, 246, 0.2)`)、HUD 角标装饰。
* **动效**：实时跳动数字时钟、环形进度发光动画、划线淡出、底部 5s 倒计时进度条 Toast。

### 2. 响应式布局策略 (电脑 + 手机兼顾)
* **电脑端 (Desktop ≥ 1024px)**：标准科技总控三栏并列：
  * 左区：昨日战报 + 成果档案柜
  * 中区：全局进度作战沙盘 + 头条/百家号持续化运行守护盘 (带日志抽屉)
  * 右区：今日作战计划 (Top-3 + 待办流 + 拖拽 + 5s撤销) + SDLC 6 阶段流水线
  * 底部：常驻 HUD 快捷指令行
* **手机端 (Mobile < 1024px)**：
  * 顶部常驻简报指标与时间；
  * 内容区采用平滑垂直卡片流排布（或底部 Tab 切换：`[今日行动]` / `[昨日进展]` / `[全局沙盘]` / `[持续化]`）；
  * 触控友好，按钮防误触，大尺寸勾选框。
