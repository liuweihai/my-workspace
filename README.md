# My Workspace (AI 自动化与知识库协同工作区)

本工作区是日常学习、项目研发与自动化定时任务的主工作区。

所有生成的成果文档、技术规范与自动化报告统一接入**飞书知识库**，并通过飞书机器人实现双端（Mac / 手机）实时通知闭环。

---

## 快速导航与指南

- 📖 **[飞书知识库自动化与多 Agent 协同指南](docs/FEISHU_KNOWLEDGE_BASE_GUIDE.md)**：包含其他 AI Agent 调用方法、Mac mini 定时任务配置、多级目录树管理。
- 📋 **[项目开发与交互规范](GEMINI.md)**：代码规范、注释要求与文档沉淀强制要求。

---

## 常用工具与命令

### 1. 沉淀文档到飞书知识库（支持分类目录）
```bash
# 格式：python3 tools/feishu_client.py <文件或文本> [分类目录名]
python3 tools/feishu_client.py GEMINI.md "项目技术规范"
python3 tools/feishu_client.py daily_report.md "自动化运行报告"
```

### 2. 执行每日定时任务并推送飞书通知
```bash
python3 scripts/daily_job_runner.py
```

### 3. Mac mini 每天定时调度指令（crontab）
```bash
(crontab -l 2>/dev/null; echo "30 8 * * * cd /Users/gang/Documents/my-workspace && /usr/bin/python3 scripts/daily_job_runner.py >> ~/daily_task.log 2>&1") | crontab -
```
