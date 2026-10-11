"""
飞书 API 连通性测试脚本
用于验证 App ID / App Secret，并列出应用可见的飞书知识库空间
"""
import os
import sys
from typing import Dict, Any, List
import requests

def load_env(env_path: str = ".env") -> Dict[str, str]:
    """读取简单的 .env 文件"""
    env_vars: Dict[str, str] = {}
    if not os.path.exists(env_path):
        return env_vars
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()
    return env_vars

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    res.raise_for_status()
    data: Dict[str, Any] = res.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取租户凭证失败 [{data.get('code')}]: {data.get('msg')}")
    token: str = data.get("tenant_access_token", "")
    return token

def list_wiki_spaces(token: str) -> List[Dict[str, Any]]:
    """查询知识库空间列表"""
    url = "https://open.feishu.cn/open-apis/wiki/v2/spaces"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers, timeout=10)
    print("API 响应状态码:", res.status_code)
    print("API 响应内容:", res.text)
    res.raise_for_status()
    data: Dict[str, Any] = res.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取知识库列表失败 [{data.get('code')}]: {data.get('msg')}")
    items: List[Dict[str, Any]] = data.get("data", {}).get("items", [])
    return items

def main() -> None:
    env_vars = load_env()
    app_id = env_vars.get("FEISHU_APP_ID", "")
    app_secret = env_vars.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        print("错误：未找到 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        sys.exit(1)

    print(f"正在测试飞书凭证 (App ID: {app_id})...")
    try:
        token = get_tenant_access_token(app_id, app_secret)
        print("✅ 凭据校验成功！已获取 tenant_access_token")
    except Exception as e:
        print(f"❌ 凭据校验失败: {e}")
        sys.exit(1)

    print("\n正在查询当前应用可见的知识库空间...")
    try:
        spaces = list_wiki_spaces(token)
        if not spaces:
            print("⚠️ 未发现可见的知识库空间。")
            print("提示：需要进入飞书知识库空间设置，将该应用添加为知识库空间成员，或在开放平台开通相应权限。")
        else:
            print(f"✅ 找到 {len(spaces)} 个知识库空间：")
            for sp in spaces:
                name = sp.get("name", "未命名")
                space_id = sp.get("space_id", "")
                space_type = sp.get("space_type", "")
                print(f"  - 名称: {name} | Space ID: {space_id} | 类型: {space_type}")
    except Exception as e:
        print(f"❌ 查询知识库出错: {e}")

if __name__ == "__main__":
    main()
