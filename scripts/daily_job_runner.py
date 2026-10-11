"""
每日定时任务调度与专属机器人通知器
功能：
1. 执行每日定时业务任务
2. 将结果同步至飞书知识库
3. 通过专属机器人（Webhook 或 Bot 私信）推送执行结果
"""
import os
import sys
import datetime
import json
import requests
from typing import Dict, Any, Optional

# 引入飞书知识库同步工具
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.feishu_client import FeishuWikiSync

class DailyTaskRunner:
    def __init__(self) -> None:
        self.wiki_sync = FeishuWikiSync()
        self.today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    def run_daily_business(self) -> Dict[str, Any]:
        """
        此处放置您每日要执行的核心业务逻辑
        例如：抓取分析热点、整理系统状态、生成日报草稿等
        """
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 正在执行每日核心任务...")
        
        # 示例：生成一份今日晨报总结
        content_markdown = f"""# 每日自动化运行报告 ({self.today_str})

> 任务触发时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 执行机器：macOS (Mac mini / 本地常驻服务)

## 今日运行概况
- **系统状态**：所有监控服务运行正常
- **工作区同步**：已对齐 GitHub 最新代码
- **知识库归档**：完成每日报告归档沉淀

## 待办与计划
- [x] 自动拉取最新热点与任务数据
- [x] 同步沉淀至飞书知识库
- [ ] 等待人工查阅与进一步决策
"""
        doc_title = f"每日自动化运行报告-{self.today_str}"
        return {"title": doc_title, "content": content_markdown}

    def send_dedicated_bot_notification(self, title: str, doc_url: str, custom_webhook: Optional[str] = None) -> None:
        """通过专属机器人发送完成通知"""
        webhook_url = custom_webhook or os.environ.get("DAILY_BOT_WEBHOOK") or self.wiki_sync.webhook_url
        
        card_content = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": f"⏰ 每日任务已成功执行完成 ({self.today_str})"},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**任务摘要**：\n今日自动化任务已顺利跑完，已沉淀知识库文档：**{title}**\n\n点击下方按钮可直接在飞书查看完整归档报告。"
                        }
                    },
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "📖 查看知识库报告"},
                                "type": "primary",
                                "url": doc_url
                            }
                        ]
                    }
                ]
            }
        }

        # 1. 优先使用专属 Webhook 推送
        if webhook_url:
            res = requests.post(webhook_url, json=card_content, timeout=10)
            if res.status_code == 200:
                print("🔔 专属群机器人卡片通知发送成功！")
                return

        # 2. 备选方案：使用自建应用私信推送
        print("未检测到独立 Webhook，回退为应用单聊私信通知...")
        self.wiki_sync.send_notification(title, doc_url)

    def execute(self, webhook_url: Optional[str] = None) -> None:
        """完整执行流：业务执行 -> 知识库保存 -> 专属机器人通知"""
        print(f"=== 开始执行每日自动化任务 ({self.today_str}) ===")
        # 1. 跑任务
        result = self.run_daily_business()
        title = result["title"]
        content = result["content"]

        # 2. 存知识库
        print("正在归档到飞书知识库...")
        sync_result = self.wiki_sync.save_markdown_to_wiki(title, content, notify=False)
        doc_url = sync_result.get("url", "")

        # 3. 专属机器人通知
        print("正在发送专属机器人完成通知...")
        self.send_dedicated_bot_notification(title, doc_url, custom_webhook=webhook_url)
        print(f"=== 每日自动化任务圆满完成！===\n")

if __name__ == "__main__":
    runner = DailyTaskRunner()
    runner.execute()
