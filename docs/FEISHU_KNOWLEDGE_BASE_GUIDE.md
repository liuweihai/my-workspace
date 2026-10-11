# 飞书知识库自动化沉淀与多 Agent 协同指南

本指南供 **用户本人** 以及 **任何 AI Agent（如 Antigravity、Claude Code、Cursor、Devin 等）** 查阅与遵循。

---

## 1. 核心设计原则

- **云端中心化**：所有生成的长篇方案、技术规范、调研报告、学习笔记以及每日自动化任务，统一自动沉淀至飞书知识库，**禁止**在本地保留散碎临时文件。
- **目录树分类归档**：知识沉淀必须进入指定分类目录（如 `📁 项目技术规范`、`📁 自动化运行报告`、`📁 每日热点资讯`、`📁 学习研究笔记` 等），不允许散落在根目录。
- **双端通知闭环**：文档沉淀成功后，飞书机器人自动向用户个人飞书私信发送富文本卡片通知，实现手机与多台 Mac 实时触达。

---

## 2. 其它 AI Agent 的使用方法（极简调用）

当任何 AI Agent 编写完成一份 Markdown 文档（或长文本内容）后，**严禁自行创建新的同步工具**，统一使用现有脚本：

### 命令格式
```bash
python3 tools/feishu_client.py <文件路径或文本内容> [分类目录名]
```

### 调用示例
```bash
# 1. 沉淀架构方案或技术规范到【项目技术规范】目录
python3 tools/feishu_client.py docs/specs/auth_system.md "项目技术规范"

# 2. 沉淀每日任务/巡检报告到【自动化运行报告】目录
python3 tools/feishu_client.py reports/daily_summary.md "自动化运行报告"

# 3. 沉淀学习心得或调研到【学习研究笔记】目录
python3 tools/feishu_client.py "React 19 Server Components 核心机制解析..." "学习研究笔记"

# 4. 沉淀热点早报到【每日热点资讯】目录
python3 tools/feishu_client.py hotnews.md "每日热点资讯"
```

> **自动化特性**：
> - 如果指定分类目录不存在，脚本会**自动在飞书知识库中新建父级目录节点**；
> - 如果已存在该目录，脚本会自动将其挂载为该目录下的**子页面**；
> - 同步成功后，脚本会自动向用户的飞书单聊私信推送带有直达链接的交互卡片。

---

## 3. 跨设备协同（Mac 笔记本 与 Mac mini）

工作区代码已托管在 GitHub 仓库：`https://github.com/liuweihai/my-workspace`。

### 修改端（写代码/修改配置后）
```bash
git add .
git commit -m "feat: 你的改动说明"
git push
```

### 接收端（在 Mac mini 或另一台电脑上）
```bash
cd ~/Documents/my-workspace
git pull
```

---

## 4. Mac mini 每日定时任务（无人值守自动跑）

由于 Mac mini 通常 24 小时开机，适合作为自动化定时任务的主机。

### 配置每日定时运行（以每天早上 8:30 为例）
在 Mac mini 终端中直接执行：
```bash
(crontab -l 2>/dev/null; echo "30 8 * * * cd /Users/gang/Documents/my-workspace && /usr/bin/python3 scripts/daily_job_runner.py >> ~/daily_task.log 2>&1") | crontab -
```

### 查看与修改定时任务
- 查看当前定时任务：`crontab -l`
- 编辑定时任务时间：`crontab -e`
- 查看每日执行日志：`cat ~/daily_task.log`

---

## 5. 配置文件说明 (`.env`)

本目录下的 `.env` 文件包含飞书开放平台的核心凭据（已被 `.gitignore` 保护，**严禁提交至 GitHub**）：

```bash
FEISHU_APP_ID=cli_xxxxxxxxxxxx          # 飞书自建应用 App ID (查看 .env)
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxx # 飞书自建应用 Secret (查看 .env)
FEISHU_SPACE_ID=xxxxxxxxxxxxxxxxxxx    # 目标飞书知识库 Space ID (查看 .env)
FEISHU_USER_OPEN_ID=ou_xxxxxxxxxxxxxxx # 用户个人的 Open ID (查看 .env)
# DAILY_BOT_WEBHOOK=                   # 可选：特定群机器人 Webhook（方案 B 备用）
```
