---
name: server-manage
description: >-
  当用户需要管理远程服务器时使用此技能。包括检查服务状态、部署网站、
  管理定时任务(cron)、查看日志、重启服务等操作。通过 SSH MCP 工具执行远程命令。
---

# 服务器管理技能

## 前提
- 已配置 `my-server` SSH MCP Server
- 所有命令通过 SSH MCP 工具在远程服务器上执行

## 常用操作

### 1. 服务状态检查
```bash
# 检查 Nginx
systemctl status nginx

# 检查正在运行的服务
systemctl list-units --type=service --state=running

# 查看端口占用
ss -tlnp

# 查看系统资源
top -bn1 | head -20
df -h
free -h
```

### 2. 网站部署
```bash
# 检查网站配置
nginx -t

# 重载 Nginx
systemctl reload nginx

# 查看网站访问日志
tail -100 /var/log/nginx/access.log

# 查看错误日志
tail -50 /var/log/nginx/error.log
```

### 3. 定时任务管理
```bash
# 查看当前用户的 cron
crontab -l

# 编辑 cron（通过 echo 追加）
# (crontab -l; echo "0 2 * * * /path/to/script.sh") | crontab -

# 查看系统级定时任务
ls -la /etc/cron.d/
cat /etc/crontab
```

### 4. 日志查看
```bash
# 系统日志
journalctl -n 50 --no-pager

# 按服务查看日志
journalctl -u nginx -n 50 --no-pager

# 实时查看（取最新内容）
tail -f /var/log/syslog | head -50
```

## 安全规则

> ⚠️ 执行以下操作前必须确认：
> - `rm -rf` 类危险命令 → 必须先列出将要删除的内容
> - 修改系统配置 → 必须先备份原文件
> - 重启服务 → 必须确认影响范围
