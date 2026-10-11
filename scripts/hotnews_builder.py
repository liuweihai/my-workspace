#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日热点爆款自媒体图文构建与硬性质检流水线（支持动态 1~3 张图片）
严格执行核心约定：
1. 标题长度严格控制在 20 到 28 个字符之间，文件名与 h1 100% 逐字一致。
2. 封面必须是百家号/头条标准 3:2 大字封面（带渐变遮罩、超粗黄白醒目大字、事件核实红线）。
3. 正文插图根据热门程度动态配置 0~2 张（整篇 1~3 张图，最少 1 张 3:2 头图）。
4. 必须包含完整爆款排版组件：.lead-box, .section-title, .quote-card, .interaction-bar。
5. 彻底去除任何多余标签、阅读量、作者栏、无用图注与页脚免责声明。
6. 彻底剔除所有 HTML/CSS 注释（<!-- --> 与 /* */）。
7. 所有图片 100% Base64 内嵌，纯单文件自包含。
"""

import os
import sys
import json
import base64
import re
import shutil
from datetime import datetime

GOOGLE_DRIVE_BASE = "/Users/gang/Library/CloudStorage/GoogleDrive-liugang0109@gmail.com/我的云端硬盘/AI/每日热点"
WORKSPACE_BASE = "/Users/gang/hotnews_automation/output/AI/每日热点"

def build_svg_cover(cover_img_data_uri: str, tag1: str, tag2: str, big_title_lines: list, event_fact: str, event_quote: str) -> str:
    """构建百家号/头条标准 3:2 大字封面 SVG 并转为 Data URI"""
    text_group_y = 230
    title_texts = []
    for i, line_info in enumerate(big_title_lines):
        text = line_info.get("text", "")
        color = line_info.get("color", "#ffffff")
        size = line_info.get("size", 48)
        y_offset = i * 72
        title_texts.append(
            f'<text x="0" y="{y_offset}" font-size="{size}" font-weight="900" fill="{color}" '
            f'font-family="\'PingFang SC\', \'Microsoft YaHei\', sans-serif">{text}</text>'
        )
    title_texts_rendered = "\n    ".join(title_texts)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600" width="900" height="600">
  <defs>
    <linearGradient id="coverMask" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgba(15, 23, 42, 0.35)"/>
      <stop offset="45%" stop-color="rgba(15, 23, 42, 0.65)"/>
      <stop offset="80%" stop-color="rgba(15, 23, 42, 0.92)"/>
      <stop offset="100%" stop-color="rgba(15, 23, 42, 0.98)"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.95"/>
    </filter>
  </defs>
  <image href="{cover_img_data_uri}" width="900" height="600" preserveAspectRatio="xMidYMid slice"/>
  <rect width="900" height="600" fill="url(#coverMask)"/>
  
  <g transform="translate(48, 42)">
    <rect width="130" height="38" rx="6" fill="#e11d48"/>
    <text x="65" y="26" font-size="19" font-weight="900" fill="#ffffff" text-anchor="middle" font-family="'PingFang SC', sans-serif">{tag1}</text>
  </g>
  <g transform="translate(195, 42)">
    <rect width="160" height="38" rx="6" fill="rgba(15,23,42,0.8)" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
    <text x="80" y="25" font-size="17" font-weight="700" fill="#f8fafc" text-anchor="middle" font-family="'PingFang SC', sans-serif">{tag2}</text>
  </g>

  <g transform="translate(48, {text_group_y})" filter="url(#shadow)">
    {title_texts_rendered}
  </g>

  <rect x="48" y="445" width="804" height="105" rx="10" fill="rgba(15,23,42,0.88)" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/>
  <text x="75" y="488" font-size="21" font-weight="700" fill="#facc15" font-family="'PingFang SC', sans-serif">📍 {event_fact}</text>
  <text x="75" y="525" font-size="17" font-weight="500" fill="#e2e8f0" font-family="'PingFang SC', sans-serif">{event_quote}</text>
</svg>'''
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"

def file_to_data_uri(file_path: str) -> str:
    """将本地图片文件转为 Data URI"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"图片文件未找到: {file_path}")
    ext = os.path.splitext(file_path)[1].lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def build_article_html(data: dict) -> str:
    """
    根据数据构建完整 HTML 并进行硬性断言校验
    """
    title = data.get("title", "").strip()
    
    # 规则 1 校验：标题长度严格 20~28 字
    title_len = len(title)
    if not (20 <= title_len <= 28):
        raise ValueError(f"【硬性拦截】标题长度必须在 20 到 28 个字符之间，当前为 {title_len} 字: '{title}'")

    # 规则 2 校验：最少必须包含 1 张封面底图（用于生成 3:2 大字封面）
    cover_img_path = data.get("cover_image_path", "")
    if not cover_img_path or not os.path.exists(cover_img_path):
        raise ValueError(f"【硬性拦截】最少必须提供 1 张封面底图（用于生成 3:2 大字封面），当前路径不存在: '{cover_img_path}'")

    cover_bg_data = file_to_data_uri(cover_img_path)

    # 封面大字包装
    cover_tag1 = data.get("cover_tag1", "热点追踪")
    cover_tag2 = data.get("cover_tag2", "现场直击")
    cover_big_titles = data.get("cover_big_titles", [])
    cover_fact = data.get("cover_fact", "")
    cover_quote = data.get("cover_quote", "")
    
    cover_data_uri = build_svg_cover(cover_bg_data, cover_tag1, cover_tag2, cover_big_titles, cover_fact, cover_quote)

    # 动态节点插图（0~2张）
    node_img1_path = data.get("node_image1_path", "")
    node_img2_path = data.get("node_image2_path", "")

    sec2_img_alt = data.get("sec2_img_alt", "现场场景实景图")
    sec3_img_alt = data.get("sec3_img_alt", "核心发展推进图")

    img1_box = ""
    if node_img1_path and os.path.exists(node_img1_path):
        img1_data = file_to_data_uri(node_img1_path)
        img1_box = f'''
    <div class="img-box">
      <img src="{img1_data}" alt="{sec2_img_alt}">
    </div>'''

    img2_box = ""
    if node_img2_path and os.path.exists(node_img2_path):
        img2_data = file_to_data_uri(node_img2_path)
        img2_box = f'''
    <div class="img-box">
      <img src="{img2_data}" alt="{sec3_img_alt}">
    </div>'''

    lead_strong = data.get("lead_strong", "")
    lead_body = data.get("lead_body", "")
    intro_p = data.get("intro_p", "")

    sec1_title = data.get("sec1_title", "")
    sec1_p1 = data.get("sec1_p1", "")
    sec1_p2 = data.get("sec1_p2", "")

    sec2_title = data.get("sec2_title", "")
    sec2_p1 = data.get("sec2_p1", "")
    sec2_p2 = data.get("sec2_p2", "")

    sec3_title = data.get("sec3_title", "")
    sec3_p1 = data.get("sec3_p1", "")
    sec3_p2 = data.get("sec3_p2", "")

    quote_text = data.get("quote_text", "")
    interaction_text = data.get("interaction_text", "")

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --primary: #e11d48;
      --primary-dark: #be123c;
      --text-main: #1e293b;
      --text-muted: #64748b;
      --bg-page: #f8fafc;
      --bg-card: #ffffff;
      --border: #e2e8f0;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background-color: var(--bg-page);
      color: var(--text-main);
      line-height: 1.85;
      padding: 20px 14px 60px;
      -webkit-font-smoothing: antialiased;
    }}
    .article-container {{
      max-width: 760px;
      margin: 0 auto;
      background: var(--bg-card);
      border-radius: 16px;
      padding: 30px 24px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.02);
      border: 1px solid var(--border);
    }}
    h1.article-title {{
      font-size: 25px;
      line-height: 1.42;
      font-weight: 800;
      color: #0f172a;
      margin-bottom: 24px;
      letter-spacing: -0.01em;
    }}
    .img-box {{
      width: 100%;
      border-radius: 12px;
      overflow: hidden;
      margin: 22px 0;
      box-shadow: 0 8px 22px -4px rgba(0,0,0,0.12);
    }}
    .img-box img {{
      width: 100%;
      height: auto;
      display: block;
      object-fit: cover;
      aspect-ratio: 3 / 2;
    }}
    .lead-box {{
      background: #fff1f2;
      border-left: 4px solid var(--primary);
      padding: 16px 20px;
      border-radius: 0 10px 10px 0;
      margin-bottom: 24px;
      font-size: 16px;
      color: #881337;
      font-weight: 500;
    }}
    .section-title {{
      font-size: 19px;
      font-weight: 700;
      color: #0f172a;
      margin: 30px 0 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .section-title::before {{
      content: "";
      width: 4px;
      height: 18px;
      background: var(--primary);
      border-radius: 2px;
      display: inline-block;
    }}
    p {{
      margin-bottom: 18px;
      font-size: 16px;
      color: #334155;
      text-align: justify;
    }}
    .quote-card {{
      background: #f0fdf4;
      border-left: 4px solid #16a34a;
      padding: 14px 18px;
      border-radius: 0 8px 8px 0;
      margin: 20px 0;
      font-size: 15px;
      color: #14532d;
    }}
    .interaction-bar {{
      margin-top: 40px;
      padding: 24px 20px;
      background: #f1f5f9;
      border-radius: 12px;
      text-align: center;
      font-size: 15px;
      color: #334155;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="article-container">
    <h1 class="article-title">{title}</h1>

    <div class="img-box">
      <img src="{cover_data_uri}" alt="{title}">
    </div>

    <div class="lead-box">
      <strong>{lead_strong}</strong><br>
      {lead_body}
    </div>

    <p>{intro_p}</p>

    <h2 class="section-title">{sec1_title}</h2>
    <p>{sec1_p1}</p>
    <p>{sec1_p2}</p>

    <h2 class="section-title">{sec2_title}</h2>{img1_box}
    <p>{sec2_p1}</p>
    <p>{sec2_p2}</p>

    <h2 class="section-title">{sec3_title}</h2>{img2_box}
    <p>{sec3_p1}</p>
    <p>{sec3_p2}</p>

    <div class="quote-card">
      {quote_text}
    </div>

    <div class="interaction-bar">
      {interaction_text}
    </div>
  </div>
</body>
</html>
'''

    # 规则 6 校验：彻底剔除 HTML 与 CSS 注释
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'/\*.*?\*/', '', html_content, flags=re.DOTALL)

    return html_content

def save_and_sync(title: str, html_content: str, date_str: str = None) -> tuple:
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    ws_dir = os.path.join(WORKSPACE_BASE, date_str)
    os.makedirs(ws_dir, exist_ok=True)
    ws_file = os.path.join(ws_dir, f"{title}.html")
    with open(ws_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    gd_dir = os.path.join(GOOGLE_DRIVE_BASE, date_str)
    os.makedirs(gd_dir, exist_ok=True)
    gd_file = os.path.join(gd_dir, f"{title}.html")
    shutil.copy2(ws_file, gd_file)

    return ws_file, gd_file

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            article_data = json.load(f)
        html = build_article_html(article_data)
        ws, gd = save_and_sync(article_data["title"], html)
        print(f"成功编译并双路同步:\n- 工作区: {ws}\n- 云盘: {gd}")
    else:
        print("HotNewsBuilder 就绪。使用方法: python3 hotnews_builder.py <article_data.json>")
