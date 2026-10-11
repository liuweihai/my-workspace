#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人战略总控驾驶舱 (Personal Executive Cockpit) 本地后端与数据库服务
支持 SQLite 持久化、标准 REST API、软删除回收站、5秒撤销、
头条/百家号持续化发布监控与实时日志流。
"""

import os
import sys
import json
import sqlite3
import datetime
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workbench.db")
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8765

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. 任务表 (支持软删除、排序)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'task',
        status TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'normal',
        project_id TEXT,
        due_date TEXT,
        is_deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT,
        completed_at TEXT
    )
    """)

    # 兼容历史库：如果已存在 tasks 表但缺少 is_deleted 等列，执行自动迁移
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    if "is_deleted" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN is_deleted INTEGER DEFAULT 0")
    if "deleted_at" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN deleted_at TEXT")
    if "sort_order" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN sort_order INTEGER DEFAULT 0")
    
    # 2. 阶段项目表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        status_text TEXT,
        progress INTEGER DEFAULT 0,
        summary TEXT,
        decision TEXT,
        next_step TEXT,
        milestones_json TEXT DEFAULT '[]',
        retros_json TEXT DEFAULT '{}',
        artifacts_json TEXT DEFAULT '[]',
        updated_at TEXT
    )
    """)
    
    # 3. 持续化与自动化守护任务表 (头条、百家号、后台监控)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS continuous_tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        platform TEXT,
        status TEXT DEFAULT 'idle',
        progress INTEGER DEFAULT 0,
        streak_days INTEGER DEFAULT 0,
        last_run_at TEXT,
        logs_json TEXT DEFAULT '[]',
        created_at TEXT
    )
    """)

    # 4. 避坑与准则表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rules (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'rule',
        content TEXT NOT NULL,
        created_at TEXT
    )
    """)
    
    # 5. 撤销日志表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS undo_logs (
        id TEXT PRIMARY KEY,
        action_type TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        prev_data TEXT NOT NULL,
        created_at TEXT
    )
    """)

    # 6. 审计日志表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS action_audit_logs (
        id TEXT PRIMARY KEY,
        action_type TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        created_at TEXT
    )
    """)
    
    # 种子数据初始化
    seed_data(cursor)
    conn.commit()
    conn.close()

def seed_data(cursor):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d 18:30:00")
    
    # 检查 continuous_tasks 是否为空
    cursor.execute("SELECT COUNT(*) FROM continuous_tasks")
    if cursor.fetchone()[0] == 0:
        toutiao_logs = [
            {"time": "07:00:10", "level": "INFO", "msg": "定时调度：启动全网热点抓取流水线 (百度/头条)"},
            {"time": "07:01:25", "level": "INFO", "msg": "热点捕获：买9斤蜜薯仅退款事件，标题严格锁定 28 字"},
            {"time": "07:01:50", "level": "SUCCESS", "msg": "生成 3:2 大字自媒体封面与纯 Base64 离线长文"},
            {"time": "07:02:15", "level": "INFO", "msg": "成果物已写入 Mac mini 远程服务器并同步至 Google Drive"}
        ]
        baijiahao_logs = [
            {"time": "07:03:00", "level": "INFO", "msg": "拉取头条母版长文，执行平台格式兼容排版"},
            {"time": "07:04:10", "level": "SUCCESS", "msg": "去 AI 味检测通过 (0% 八股词汇)，配图已内嵌"},
            {"time": "07:05:00", "level": "INFO", "msg": "百家号草稿分发已就绪，等待最佳发刊时机"}
        ]
        cursor.execute("""
        INSERT INTO continuous_tasks (id, title, platform, status, progress, streak_days, last_run_at, logs_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "toutiao-auto", "今日头条长文自动抓取与发布", "toutiao", "active", 90, 12, "今日 07:02", json.dumps(toutiao_logs, ensure_ascii=False), now
        ))
        cursor.execute("""
        INSERT INTO continuous_tasks (id, title, platform, status, progress, streak_days, last_run_at, logs_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "baijiahao-auto", "百家号图文矩阵自动分发", "baijiahao", "active", 85, 9, "今日 07:05", json.dumps(baijiahao_logs, ensure_ascii=False), now
        ))

    # 检查 projects 是否为空
    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        projects = [
            (
                "wechat-article",
                "公众号深度长文项目",
                "active",
                "🔴 重点攻坚中",
                15,
                "打造具备深度、高粘性与自媒体审美的公众号深度长文产出链路。",
                "当前列为首要攻坚方向。核心痛点是传统 AI 写法太假、缺乏结构化深度。",
                "挑选 1 个行业破局选题打样第一篇深度母版样章",
                json.dumps(["选题策略草案", "首篇深度样章"], ensure_ascii=False),
                json.dumps(["待生成首篇标准样章"], ensure_ascii=False),
                now
            ),
            (
                "daily-hot-news",
                "每日热点自媒体自动化",
                "hold",
                "🟡 搁置待命中",
                90,
                "每日早晨 07:00 自动抓取百度/头条热点，输出 28 字、3:2 大字封面、全 Base64 纯净长文。",
                "已完成首件高标准打样与 sidecar 任务配置。搁置原因：先理清完整发布流程，暂不开启定时调度，后续随时一键启用。",
                "待发布闭环理顺后，在 Automations 控制台一键启用定时调度",
                json.dumps(["抓取解析", "模板排版", "定时发布"], ensure_ascii=False),
                json.dumps([
                    "远程服务器: output/2026-10-10/买9斤蜜薯仅退款...html",
                    "Google Drive: AI/每日热点/2026-10-10/买9斤蜜薯仅退款...html"
                ], ensure_ascii=False),
                now
            ),
            (
                "intranet-access",
                "Mac mini 网站外网访问",
                "hold",
                "🟡 搁置待命中",
                80,
                "实现外部随时访问内网 Mac mini 部署的多个 Web 服务（OpenClaw 18789、Python 8790 等）。",
                "技术方案已完成严格论证与对比，选定最优解为 Tailscale 异地组网（零域名、零成本、P2P 极速直连）。搁置原因：暂无紧急外部访问需求，方案归档备用。",
                "后续需要时，在 Mac mini 执行一条安装命令，5 分钟即可彻底打通",
                json.dumps(["网络选型", "Tailscale验证", "端口映射"], ensure_ascii=False),
                json.dumps(["Tailscale 零域名组网技术方案备忘"], ensure_ascii=False),
                now
            ),
            (
                "ssh-mcp",
                "Mac mini 远程 SSH MCP 通道",
                "done",
                "🟢 已闭环资产",
                100,
                "打通专属 my-server SSH MCP 原生工具集，实现对局域网 M4 Mac mini 的全自动零弹窗管理。",
                "已完全取代旧的终端沙箱外部调用，彻底根除频繁弹窗确认问题。",
                "已常驻运行，作为所有远程脚本部署与文件同步的底层支撑通道",
                json.dumps(["密钥配对", "MCP工具注册", "无弹窗验证"], ensure_ascii=False),
                json.dumps([
                    "my-server MCP 配置 (~/.gemini/config/mcp_config.json)",
                    "远程工具集: remote-ssh, ssh-write-chunk, ssh-read-lines"
                ], ensure_ascii=False),
                now
            ),
            (
                "delivery-engine",
                "通用任务标准化交付 SOP",
                "done",
                "🟢 已闭环资产",
                100,
                "确立 5 步标准化交付流水线（探针 ➜ 打样 ➜ 双保险 ➜ 调度 ➜ 验收），并固化去 AI 味核心铁律。",
                "作为所有新需求的元工作流标准，杜绝反复无效沟通与假模版。",
                "后续开启任何新项目时直接激活该技能作为守则",
                json.dumps(["探针探测", "首件打样", "双保险", "正式调度", "验收归档"], ensure_ascii=False),
                json.dumps([
                    ".agents/skills/task-delivery-engine/SKILL.md",
                    ".agents/skills/spec-driven-dev/SKILL.md"
                ], ensure_ascii=False),
                now
            )
        ]
        cursor.executemany("""
        INSERT INTO projects (id, title, status, status_text, progress, summary, decision, next_step, milestones_json, artifacts_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, projects)

    # 检查 tasks 是否为空
    cursor.execute("SELECT COUNT(*) FROM tasks")
    if cursor.fetchone()[0] == 0:
        tasks = [
            ("task-1", "【焦点】公众号长文：梳理首期 MVP 与选题打样", "task", "pending", "top3", "wechat-article", "今日", 0, None, 1, now, None),
            ("task-2", "【体验】测试驾驶舱打勾即完成与 5 秒撤销动效", "task", "pending", "top3", None, "今日", 0, None, 2, now, None),
            ("task-3", "【自媒体】梳理 3 个兼具话题度与深度的公众号破局选题", "task", "pending", "high", "wechat-article", "今日", 0, None, 3, now, None),
            ("task-4", "【待命】头条/百家号自动化发布监控与近况日志巡检", "task", "pending", "normal", "daily-hot-news", "今日", 0, None, 4, now, None),
            # 昨日战报记录
            ("task-y1", "打通 M4 Mac mini 局域网 SSH 原生 MCP 通道", "task", "done", "normal", "ssh-mcp", "昨日", 0, None, 5, yesterday, yesterday),
            ("task-y2", "固化通用任务标准化交付 SOP 与去 AI 味铁律", "task", "done", "normal", "delivery-engine", "昨日", 0, None, 6, yesterday, yesterday),
            ("task-y3", "生成每日热点长文单文件首件打样 HTML", "task", "done", "normal", "daily-hot-news", "昨日", 0, None, 7, yesterday, yesterday),
        ]
        cursor.executemany("""
        INSERT INTO tasks (id, title, category, status, priority, project_id, due_date, is_deleted, deleted_at, sort_order, created_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tasks)

    # 检查 rules 是否为空
    cursor.execute("SELECT COUNT(*) FROM rules")
    if cursor.fetchone()[0] == 0:
        rules = [
            ("rule-1", "标题严格 ≤ 28 字符硬约束", "format", "标题加所有标点严格 ≤ 28 字，文件名与文章首行 h1 必须逐字完全一致，杜绝任何机械腰斩。", now),
            ("rule-2", "去 AI 味核心准则 (真人纪实风)", "writing", "严禁“多维透视、协同推进、总的来说、不可否认”等公文腔八股；多用客观事实、真人对话口吻与具体数字切中痛点。", now),
            ("rule-3", "成果物纯单文件自包含", "format", "首图 3:2 封面，所有配图经由 Base64 深度内嵌，代码彻底零注释，双击离线秒开，无外部 CDN 损坏风险。", now),
            ("rule-4", "SOP 五步交付铁律", "workflow", "1.探针先行确认环境 ➜ 2.首件打样对齐标准 ➜ 3.双保险防呆 ➜ 4.正式调度 ➜ 5.带清单验收闭环。", now)
        ]
        cursor.executemany("""
        INSERT INTO rules (id, title, category, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, rules)

class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # 首页直接呈现总控驾驶舱
        if path == "/" or path == "/dashboard.html":
            file_path = os.path.join(STATIC_DIR, "dashboard.html")
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "dashboard.html not found")
                return

        # V1 全盘大屏状态聚合
        if path == "/api/v1/state" or path == "/api/state":
            self.handle_get_state()
            return

        # 自动化发布流水与 publisher.db 真实数据
        if path in ("/api/v1/publisher/data", "/api/publisher/data"):
            self.handle_get_publisher_data()
            return
            
        # 回收站
        if path == "/api/v1/recycle_bin":
            self.handle_get_recycle_bin()
            return

        # 健康探针
        if path == "/api/health" or path == "/api/v1/health":
            self._send_json({"status": "ok", "time": datetime.datetime.now().isoformat(), "db": DB_PATH})
            return

        # 静态文件服务
        clean_path = path.lstrip("/")
        local_path = os.path.join(STATIC_DIR, clean_path)
        if os.path.exists(local_path) and os.path.isfile(local_path):
            with open(local_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self._send_cors_headers()
            if local_path.endswith(".json"):
                self.send_header("Content-Type", "application/json; charset=utf-8")
            elif local_path.endswith(".js"):
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
            elif local_path.endswith(".css"):
                self.send_header("Content-Type", "text/css; charset=utf-8")
            else:
                self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            payload = {}

        # 任务相关
        if path in ("/api/v1/tasks/toggle", "/api/task/toggle"):
            self.handle_toggle_task(payload)
        elif path in ("/api/v1/tasks/undo", "/api/task/undo"):
            self.handle_undo_task(payload)
        elif path in ("/api/v1/tasks/create", "/api/task/create"):
            self.handle_create_task(payload)
        elif path in ("/api/v1/tasks/update", "/api/task/update"):
            self.handle_update_task(payload)
        elif path in ("/api/v1/tasks/delete", "/api/task/delete"):
            self.handle_soft_delete_task(payload)
        elif path in ("/api/v1/tasks/restore", "/api/task/restore"):
            self.handle_restore_task(payload)
            
        # 项目相关
        elif path in ("/api/v1/projects/update", "/api/project/update"):
            self.handle_update_project(payload)
            
        # 持续化任务与自动化日志上报
        elif path in ("/api/v1/continuous/ping", "/api/continuous/ping"):
            self.handle_continuous_ping(payload)
            
        # 规则添加
        elif path in ("/api/v1/rules/create", "/api/rule/create"):
            self.handle_create_rule(payload)
        else:
            self.send_error(404, "Endpoint not found")

    def handle_get_state(self):
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. 活跃任务 (未删除)
        cursor.execute("SELECT * FROM tasks WHERE is_deleted = 0 ORDER BY sort_order ASC, created_at DESC")
        all_active = [dict(row) for row in cursor.fetchall()]
        
        # 今日待办 vs 昨日战报
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        today_tasks = [t for t in all_active if t["status"] == "pending"]
        done_tasks = [t for t in all_active if t["status"] == "done"]
        
        # 昨日完成战报: completed_at 包含昨日或标记为昨日
        yesterday_recap = [
            t for t in done_tasks 
            if (t.get("completed_at") and t["completed_at"].startswith(yesterday_date)) or t.get("due_date") == "昨日"
        ]
        # 如果昨日较少，补充最近完成的 3 条
        if len(yesterday_recap) < 3:
            for d in done_tasks:
                if d not in yesterday_recap:
                    yesterday_recap.append(d)
                if len(yesterday_recap) >= 4:
                    break

        # 2. 阶段项目
        cursor.execute("SELECT * FROM projects ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'hold' THEN 2 ELSE 3 END, updated_at DESC")
        projects_raw = [dict(row) for row in cursor.fetchall()]
        projects = []
        for p in projects_raw:
            try:
                p["artifacts"] = json.loads(p.get("artifacts_json") or "[]")
            except Exception:
                p["artifacts"] = []
            try:
                p["milestones"] = json.loads(p.get("milestones_json") or "[]")
            except Exception:
                p["milestones"] = []
            projects.append(p)
            
        # 3. 持续化任务 (头条、百家号)
        cursor.execute("SELECT * FROM continuous_tasks ORDER BY created_at ASC")
        continuous_raw = [dict(row) for row in cursor.fetchall()]
        continuous_tasks = []
        for c in continuous_raw:
            try:
                c["logs"] = json.loads(c.get("logs_json") or "[]")
            except Exception:
                c["logs"] = []
            continuous_tasks.append(c)

        # 4. 准则
        cursor.execute("SELECT * FROM rules ORDER BY created_at DESC")
        rules = [dict(row) for row in cursor.fetchall()]
        
        # 5. 回收站数量
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE is_deleted = 1")
        recycle_count = cursor.fetchone()[0]

        # 6. 最新撤销快照
        cursor.execute("SELECT * FROM undo_logs ORDER BY created_at DESC LIMIT 1")
        last_undo_row = cursor.fetchone()
        last_undo = dict(last_undo_row) if last_undo_row else None

        conn.close()

        self._send_json({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stats": {
                "active_projects": sum(1 for p in projects if p["status"] == "active"),
                "hold_projects": sum(1 for p in projects if p["status"] == "hold"),
                "done_projects": sum(1 for p in projects if p["status"] == "done"),
                "pending_tasks": len(today_tasks),
                "done_tasks": len(done_tasks),
                "continuous_count": len(continuous_tasks),
                "recycle_count": recycle_count
            },
            "today_tasks": today_tasks,
            "done_tasks": done_tasks,
            "yesterday_recap": yesterday_recap,
            "projects": projects,
            "continuous_tasks": continuous_tasks,
            "rules": rules,
            "last_undo": last_undo
        })

    def handle_toggle_task(self, payload):
        task_id = payload.get("id")
        target_status = payload.get("status") # 支持显式指定（拖拽场景）
        if not task_id:
            self._send_json({"error": "Missing task id"}, status_code=400)
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            conn.close()
            self._send_json({"error": "Task not found"}, status_code=404)
            return

        prev_task = dict(task_row)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if target_status:
            new_status = target_status
            completed_at = now if new_status == "done" else None
        else:
            if prev_task["status"] == "done":
                new_status = "pending"
                completed_at = None
            else:
                new_status = "done"
                completed_at = now

        cursor.execute("""
        UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?
        """, (new_status, completed_at, task_id))

        # 写入撤销栈与审计日志
        undo_id = f"undo-{int(datetime.datetime.now().timestamp() * 1000)}"
        cursor.execute("""
        INSERT INTO undo_logs (id, action_type, entity_type, entity_id, prev_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (undo_id, "toggle_task", "task", task_id, json.dumps(prev_task, ensure_ascii=False), now))

        cursor.execute("""
        INSERT INTO action_audit_logs (id, action_type, entity_type, entity_id, snapshot_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (f"audit-{undo_id}", "toggle_task", "task", task_id, json.dumps(prev_task, ensure_ascii=False), now))

        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        updated_task = dict(cursor.fetchone())
        conn.close()

        self._send_json({
            "success": True,
            "task": updated_task,
            "undo_id": undo_id,
            "message": f"任务已变更为「{'已完成' if new_status == 'done' else '进行中'}」"
        })

    def handle_undo_task(self, payload):
        undo_id = payload.get("undo_id")
        conn = get_db()
        cursor = conn.cursor()

        if undo_id:
            cursor.execute("SELECT * FROM undo_logs WHERE id = ?", (undo_id,))
        else:
            cursor.execute("SELECT * FROM undo_logs ORDER BY created_at DESC LIMIT 1")
            
        undo_row = cursor.fetchone()
        if not undo_row:
            conn.close()
            self._send_json({"error": "当前没有可撤销的操作"}, status_code=400)
            return

        undo_data = dict(undo_row)
        prev_data = json.loads(undo_data["prev_data"])
        
        if undo_data["entity_type"] == "task":
            cursor.execute("""
            UPDATE tasks SET 
                title = ?,
                status = ?,
                priority = ?,
                is_deleted = ?,
                deleted_at = ?,
                completed_at = ?
            WHERE id = ?
            """, (
                prev_data["title"],
                prev_data["status"],
                prev_data.get("priority", "normal"),
                prev_data.get("is_deleted", 0),
                prev_data.get("deleted_at"),
                prev_data.get("completed_at"),
                prev_data["id"]
            ))
            
            cursor.execute("DELETE FROM undo_logs WHERE id = ?", (undo_data["id"],))
            conn.commit()
            
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (prev_data["id"],))
            restored = dict(cursor.fetchone())
            conn.close()
            
            self._send_json({
                "success": True,
                "restored_task": restored,
                "message": f"已撤销操作，任务「{restored['title']}」已原位恢复！"
            })
        else:
            conn.close()
            self._send_json({"error": "暂不支持该类型的撤销"}, status_code=400)

    def handle_create_task(self, payload):
        title = payload.get("title", "").strip()
        if not title:
            self._send_json({"error": "Title required"}, status_code=400)
            return

        task_id = f"task-{int(datetime.datetime.now().timestamp() * 1000)}"
        priority = payload.get("priority", "normal")
        category = payload.get("category", "task")
        project_id = payload.get("project_id") or None
        due_date = payload.get("due_date", "今日")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        cursor = conn.cursor()

        # 唯一性防重校验：如果今日未完成待办中已存在同名任务，拒绝重复插入
        cursor.execute("SELECT id, title, status FROM tasks WHERE title = ? AND is_deleted = 0 AND status = 'pending'", (title,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            self._send_json({
                "success": False,
                "error": "该行动已在今日计划中，无需重复添加",
                "duplicate": True,
                "task": dict(existing)
            }, status_code=409)
            return

        cursor.execute("""
        INSERT INTO tasks (id, title, category, status, priority, project_id, due_date, is_deleted, created_at)
        VALUES (?, ?, ?, 'pending', ?, ?, ?, 0, ?)
        """, (task_id, title, category, priority, project_id, due_date, now))
        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = dict(cursor.fetchone())
        conn.close()

        self._send_json({"success": True, "task": task})

    def handle_get_publisher_data(self):
        pub_db = os.path.join(STATIC_DIR, "baijiahao", "data", "publisher.db")
        if not os.path.exists(pub_db):
            self._send_json({"error": "publisher.db 数据库不存在", "jobs": [], "tasks": []}, status_code=200)
            return

        try:
            conn = sqlite3.connect(pub_db)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # 1. 查询 publish_jobs 联查关联的 publish_articles
            c.execute("""
            SELECT j.id, datetime(j.created_at, 'unixepoch', 'localtime') as created_at_fmt,
                   j.status, j.platforms, j.auto_publish, j.current_platform, j.current_index, j.last_error,
                   a.title as article_title, a.html_path, a.cover_path
            FROM publish_jobs j
            LEFT JOIN publish_articles a ON j.id = a.job_id
            ORDER BY j.created_at DESC LIMIT 30
            """)
            jobs = [dict(r) for r in c.fetchall()]

            # 2. 查询 publish_tasks
            c.execute("""
            SELECT t.id, t.job_id, t.platform, t.status, t.stage, t.error,
                   datetime(t.updated_at, 'unixepoch', 'localtime') as updated_at_fmt,
                   t.account_name, a.title as article_title
            FROM publish_tasks t
            LEFT JOIN publish_articles a ON t.job_id = a.job_id
            ORDER BY t.updated_at DESC LIMIT 50
            """)
            tasks = [dict(r) for r in c.fetchall()]

            # 3. 查询 automation_jobs & monitor_seen
            c.execute("""
            SELECT job_id, source_type, source_key, fingerprint, datetime(publish_at, 'unixepoch', 'localtime') as publish_at_fmt, status
            FROM automation_jobs ORDER BY created_at DESC LIMIT 20
            """)
            automation_jobs = [dict(r) for r in c.fetchall()]

            conn.close()

            self._send_json({
                "status": "ok",
                "db_path": pub_db,
                "jobs": jobs,
                "tasks": tasks,
                "automation_jobs": automation_jobs
            })
        except Exception as e:
            self._send_json({"error": str(e), "jobs": [], "tasks": []}, status_code=500)

    def handle_update_task(self, payload):
        task_id = payload.get("id")
        if not task_id:
            self._send_json({"error": "Missing task id"}, status_code=400)
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            self._send_json({"error": "Task not found"}, status_code=404)
            return

        updates = []
        params = []
        if "title" in payload and payload["title"].strip():
            updates.append("title = ?")
            params.append(payload["title"].strip())
        if "priority" in payload:
            updates.append("priority = ?")
            params.append(payload["priority"])
        if "project_id" in payload:
            updates.append("project_id = ?")
            params.append(payload["project_id"] or None)
        if "due_date" in payload:
            updates.append("due_date = ?")
            params.append(payload["due_date"])

        if updates:
            params.append(task_id)
            cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        updated = dict(cursor.fetchone())
        conn.close()
        self._send_json({"success": True, "task": updated})

    def handle_soft_delete_task(self, payload):
        task_id = payload.get("id")
        if not task_id:
            self._send_json({"error": "Task id required"}, status_code=400)
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            prev_data = dict(row)
            cursor.execute("UPDATE tasks SET is_deleted = 1, deleted_at = ? WHERE id = ?", (now, task_id))
            
            undo_id = f"undo-{int(datetime.datetime.now().timestamp() * 1000)}"
            cursor.execute("""
            INSERT INTO undo_logs (id, action_type, entity_type, entity_id, prev_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (undo_id, "delete_task", "task", task_id, json.dumps(prev_data, ensure_ascii=False), now))
            
            cursor.execute("""
            INSERT INTO action_audit_logs (id, action_type, entity_type, entity_id, snapshot_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (f"audit-{undo_id}", "delete_task", "task", task_id, json.dumps(prev_data, ensure_ascii=False), now))
            conn.commit()

        conn.close()
        self._send_json({"success": True, "deleted_id": task_id, "undo_id": undo_id})

    def handle_restore_task(self, payload):
        task_id = payload.get("id")
        if not task_id:
            self._send_json({"error": "Task id required"}, status_code=400)
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET is_deleted = 0, deleted_at = NULL WHERE id = ?", (task_id,))
        conn.commit()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        self._send_json({"success": True, "task": dict(row) if row else None})

    def handle_get_recycle_bin(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE is_deleted = 1 ORDER BY deleted_at DESC")
        deleted = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self._send_json({"deleted_tasks": deleted})

    def handle_update_project(self, payload):
        p_id = payload.get("id")
        if not p_id:
            self._send_json({"error": "Project id required"}, status_code=400)
            return

        conn = get_db()
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        status = payload.get("status")
        progress = payload.get("progress")
        next_step = payload.get("next_step")
        decision = payload.get("decision")
        
        updates = ["updated_at = ?"]
        params = [now]
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status == "active":
                updates.append("status_text = '🔴 重点攻坚中'")
            elif status == "hold":
                updates.append("status_text = '🟡 搁置待命中'")
            elif status == "done":
                updates.append("status_text = '🟢 已闭环资产'")
                
        if progress is not None:
            updates.append("progress = ?")
            params.append(int(progress))
        if next_step is not None:
            updates.append("next_step = ?")
            params.append(next_step)
        if decision is not None:
            updates.append("decision = ?")
            params.append(decision)

        params.append(p_id)
        cursor.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        cursor.execute("SELECT * FROM projects WHERE id = ?", (p_id,))
        row = cursor.fetchone()
        conn.close()
        self._send_json({"success": True, "project": dict(row) if row else None})

    def handle_continuous_ping(self, payload):
        c_id = payload.get("id")
        status = payload.get("status", "active")
        progress = payload.get("progress")
        log_msg = payload.get("log_msg")
        log_level = payload.get("log_level", "INFO")
        
        if not c_id:
            self._send_json({"error": "Missing continuous task id"}, status_code=400)
            return

        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        now_full = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM continuous_tasks WHERE id = ?", (c_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            self._send_json({"error": "Continuous task not found"}, status_code=404)
            return

        c_task = dict(row)
        try:
            logs = json.loads(c_task.get("logs_json") or "[]")
        except Exception:
            logs = []

        if log_msg:
            logs.insert(0, {"time": now_time, "level": log_level, "msg": log_msg})
            logs = logs[:20] # 保留最新 20 条日志

        updates = ["status = ?", "last_run_at = ?", "logs_json = ?"]
        params = [status, f"今日 {now_time}", json.dumps(logs, ensure_ascii=False)]

        if progress is not None:
            updates.append("progress = ?")
            params.append(int(progress))

        params.append(c_id)
        cursor.execute(f"UPDATE continuous_tasks SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        cursor.execute("SELECT * FROM continuous_tasks WHERE id = ?", (c_id,))
        updated = dict(cursor.fetchone())
        conn.close()
        self._send_json({"success": True, "continuous_task": updated})

    def handle_create_rule(self, payload):
        title = payload.get("title", "").strip()
        content = payload.get("content", "").strip()
        if not title or not content:
            self._send_json({"error": "Title and content required"}, status_code=400)
            return

        r_id = f"rule-{int(datetime.datetime.now().timestamp() * 1000)}"
        category = payload.get("category", "rule")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO rules (id, title, category, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (r_id, title, category, content, now))
        conn.commit()

        cursor.execute("SELECT * FROM rules WHERE id = ?", (r_id,))
        rule = dict(cursor.fetchone())
        conn.close()
        self._send_json({"success": True, "rule": rule})

def run_server():
    init_db()
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, WorkbenchRequestHandler)
    print(f"==================================================")
    print(f"🚀 个人战略总控驾驶舱服务就绪 (V1)！")
    print(f"📡 Web 访问地址: http://localhost:{PORT}")
    print(f"💾 本地 SQLite 库: {DB_PATH}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
