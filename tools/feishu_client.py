"""
飞书知识库自动同步与通知工具
功能：
1. 创建知识库文档节点并解析写入 Markdown 内容
2. 同步完成后自动向用户发送飞书卡片/富文本通知
"""
import os
import sys
import json
from typing import Dict, Any, List, Optional
import requests

class FeishuWikiSync:
    def __init__(self, env_file: str = ".env"):
        self.base_url = "https://open.feishu.cn/open-apis"
        self.env_vars = self._load_env(env_file)
        self.app_id = self.env_vars.get("FEISHU_APP_ID", "")
        self.app_secret = self.env_vars.get("FEISHU_APP_SECRET", "")
        self.space_id = self.env_vars.get("FEISHU_SPACE_ID", "")
        self.user_open_id = self.env_vars.get("FEISHU_USER_OPEN_ID", "")
        self.webhook_url = self.env_vars.get("FEISHU_WEBHOOK_URL", "")
        self.token: Optional[str] = None

        if not self.app_id or not self.app_secret:
            raise ValueError("未在 .env 中找到 FEISHU_APP_ID 或 FEISHU_APP_SECRET")

    def _load_env(self, env_path: str) -> Dict[str, str]:
        """读取 .env 配置"""
        config: Dict[str, str] = {}
        if not os.path.exists(env_path):
            return config
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
        return config

    def get_token(self) -> str:
        """获取并缓存 tenant_access_token"""
        if self.token:
            return self.token
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        res = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 Token 失败: {data.get('msg')}")
        self.token = data["tenant_access_token"]
        return self.token

    def create_wiki_document(self, title: str, parent_node_token: str = "") -> Dict[str, Any]:
        """在知识库中创建空白 docx 文档节点"""
        token = self.get_token()
        url = f"{self.base_url}/wiki/v2/spaces/{self.space_id}/nodes"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "obj_type": "docx",
            "node_type": "origin",
            "title": title
        }
        if parent_node_token:
            payload["parent_node_token"] = parent_node_token

        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("code") != 0:
            raise RuntimeError(f"创建知识库文档节点失败: {data.get('msg')}")
        return data["data"]["node"]

    def markdown_to_blocks(self, markdown_text: str) -> List[Dict[str, Any]]:
        """将基础 Markdown 文本转为飞书 docx blocks"""
        blocks: List[Dict[str, Any]] = []
        lines = markdown_text.split("\n")
        in_code_block = False
        code_lines: List[str] = []

        for line in lines:
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_lines = []
                    continue
                else:
                    in_code_block = False
                    code_content = "\n".join(code_lines)
                    blocks.append({
                        "block_type": 14, # Code block
                        "code": {
                            "elements": [{"text_run": {"content": code_content}}]
                        }
                    })
                    continue

            if in_code_block:
                code_lines.append(line)
                continue

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("### "):
                blocks.append({
                    "block_type": 5, # Heading 3
                    "heading3": {"elements": [{"text_run": {"content": stripped[4:]}}]}
                })
            elif stripped.startswith("## "):
                blocks.append({
                    "block_type": 4, # Heading 2
                    "heading2": {"elements": [{"text_run": {"content": stripped[3:]}}]}
                })
            elif stripped.startswith("# "):
                blocks.append({
                    "block_type": 3, # Heading 1
                    "heading1": {"elements": [{"text_run": {"content": stripped[2:]}}]}
                })
            elif stripped.startswith("- ") or stripped.startswith("* "):
                blocks.append({
                    "block_type": 12, # Bullet list
                    "bullet": {"elements": [{"text_run": {"content": stripped[2:]}}]}
                })
            elif stripped.startswith("> "):
                blocks.append({
                    "block_type": 17, # Quote
                    "quote": {"elements": [{"text_run": {"content": stripped[2:]}}]}
                })
            else:
                blocks.append({
                    "block_type": 2, # Text paragraph
                    "text": {"elements": [{"text_run": {"content": line}}]}
                })

        return blocks

    def append_document_blocks(self, document_id: str, blocks: List[Dict[str, Any]]) -> None:
        """向飞书文档写入 blocks 内容（分批次写入，单次最多50个）"""
        token = self.get_token()
        url = f"{self.base_url}/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        batch_size = 50
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            payload = {
                "children": batch,
                "index": -1
            }
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()
            if data.get("code") != 0:
                raise RuntimeError(f"写入文档内容失败: {data.get('msg')}")

    def send_notification(self, title: str, doc_url: str) -> bool:
        """向用户飞书发送文档沉淀通知"""
        # 1. 优先使用应用单聊私信通知
        if self.user_open_id:
            try:
                token = self.get_token()
                url = f"{self.base_url}/im/v1/messages?receive_id_type=open_id"
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
                content = {
                    "zh_cn": {
                        "title": f"📑 知识库沉淀完成：{title}",
                        "content": [
                            [
                                {"tag": "text", "text": "文档已自动整理并同步至飞书知识库空间。\n\n"},
                                {"tag": "a", "text": "🔗 点击在飞书中查看全文", "href": doc_url}
                            ]
                        ]
                    }
                }
                payload = {
                    "receive_id": self.user_open_id,
                    "msg_type": "post",
                    "content": json.dumps(content)
                }
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                data = res.json()
                if data.get("code") == 0:
                    print("🔔 已成功向您的飞书私信推送通知！")
                    return True
                else:
                    print(f"⚠️ 私信通知未能直达 ({data.get('msg')})")
            except Exception as e:
                print(f"⚠️ 发送私信通知异常: {e}")

        # 2. 如果配置了 Webhook，则调用 Webhook 发送
        if self.webhook_url:
            try:
                wb_payload = {
                    "msg_type": "post",
                    "content": {
                        "post": {
                            "zh_cn": {
                                "title": f"📑 知识库沉淀完成：{title}",
                                "content": [
                                    [
                                        {"tag": "text", "text": "文档已同步至知识库：\n"},
                                        {"tag": "a", "text": title, "href": doc_url}
                                    ]
                                ]
                            }
                        }
                    }
                }
                res = requests.post(self.webhook_url, json=wb_payload, timeout=10)
                if res.status_code == 200:
                    print("🔔 已通过 Webhook 推送群通知！")
                    return True
            except Exception as e:
                print(f"⚠️ Webhook 通知异常: {e}")

        return False

    def save_markdown_to_wiki(self, title: str, markdown_content: str, notify: bool = True) -> Dict[str, str]:
        """一键将 Markdown 内容保存为飞书知识库文档并触发通知"""
        print(f"正在创建飞书知识库节点: {title} ...")
        node = self.create_wiki_document(title)
        node_url = node.get("url", "")
        obj_token = node.get("obj_token", "")

        print("正在转换并写入文档内容...")
        blocks = self.markdown_to_blocks(markdown_content)
        if blocks:
            self.append_document_blocks(obj_token, blocks)

        print(f"✅ 保存成功！文档链接: {node_url}")
        
        if notify:
            self.send_notification(title, node_url)

        return {"title": title, "url": node_url, "doc_id": obj_token}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 tools/feishu_client.py <markdown文件路径或测试文本>")
        sys.exit(1)

    client = FeishuWikiSync()
    target = sys.argv[1]
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        title = os.path.splitext(os.path.basename(target))[0]
    else:
        title = "快速备忘"
        content = target

    client.save_markdown_to_wiki(title, content)
