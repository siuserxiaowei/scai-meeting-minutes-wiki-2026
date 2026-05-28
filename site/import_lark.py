#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "lark"
MINUTES_CACHE = ROOT / ".cache" / "minutes"

SHENZHEN_ROOT = "https://scailabs.feishu.cn/wiki/VswYwTzBwidqf8k5xZQcQAQTntG?from=from_copylink"
SHENZHEN_TOKEN = "VswYwTzBwidqf8k5xZQcQAQTntG"
GUANGZHOU_ROOT = "https://hvwrkfob90.feishu.cn/wiki/GGybwWTBAiLbZWkn75uc3Ev1nKb?from=from_copylink"


def ensure_dirs():
    for path in [
        CACHE,
        MINUTES_CACHE,
        ROOT / "data",
        ROOT / "events",
        ROOT / "guide",
        ROOT / "analysis",
        ROOT / "quotes",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_json_blob(text):
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def run_lark(args, cache_name=None, allow_fail=False, timeout=180):
    if cache_name:
        cache_path = CACHE / cache_name
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

    cmd = ["lark-cli", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    combined = f"{result.stdout}\n{result.stderr}"
    parsed = extract_json_blob(combined)
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"lark-cli failed ({result.returncode}): {' '.join(cmd)}\n{combined[-2000:]}")
    if parsed is None:
        parsed = {"ok": False, "returncode": result.returncode, "raw": combined[-4000:]}
    if cache_name:
        write_json(cache_path, parsed)
    return parsed


def safe_fetch_doc(url, cache_prefix):
    attempts = [
        ["docs", "+fetch", "--as", "user", "--api-version", "v2", "--doc", url, "--doc-format", "markdown", "--format", "json"],
        ["docs", "+fetch", "--api-version", "v2", "--doc", url, "--doc-format", "markdown", "--format", "json"],
    ]
    last = None
    for idx, args in enumerate(attempts):
        cache_name = f"{cache_prefix}-doc-{idx}.json"
        data = run_lark(args, cache_name=cache_name, allow_fail=True)
        if data.get("ok") is True or data.get("code") == 0:
            return data
        last = data
    return last or {"ok": False, "error": {"message": "fetch failed"}}


def fetch_minutes(url, cache_prefix):
    token = minute_token(url)
    if not token:
        return None
    args = [
        "vc",
        "+notes",
        "--as",
        "user",
        "--minute-tokens",
        token,
        "--output-dir",
        str(MINUTES_CACHE),
        "--format",
        "json",
    ]
    return run_lark(args, cache_name=f"{cache_prefix}-minutes.json", allow_fail=True, timeout=240)


def doc_content(fetch_result):
    if not fetch_result:
        return ""
    if fetch_result.get("ok") is True:
        return fetch_result.get("data", {}).get("document", {}).get("content", "") or ""
    if fetch_result.get("code") == 0:
        return fetch_result.get("data", {}).get("document", {}).get("content", "") or ""
    return ""


def slugify(value, fallback):
    value = value.lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:72] or fallback


def short_hash(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def normalize_date(text):
    match = re.search(r"(20\d{2})[-/.年]?\s*(\d{1,2})[-/.月]?\s*(\d{1,2})", text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def strip_title_prefix(title):
    return re.sub(r"^20\d{2}[-/.年]?\d{1,2}[-/.月]?\d{1,2}\s*[｜|]?\s*", "", title).strip()


def sanitize_markdown(md):
    text = md or ""
    text = re.sub(r"<readonly-block[^>]*></readonly-block>", "", text)
    text = re.sub(r"<whiteboard\b[^>]*>(?:</whiteboard>)?", "\n> [飞书白板封面已隐藏，可回到原纪要查看]\n", text)
    text = re.sub(r"<figure\b[^>]*>.*?</figure>", "\n> [飞书附件或预览已隐藏，可回到原纪要查看]\n", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\(https://internal-api-drive-stream\.feishu\.cn/[^)]+\)", "> [飞书图片临时链接已隐藏，可回到原纪要查看]", text)
    text = re.sub(r"!\[[^\]]*\]\(https://feishu\.cn/file/[^)]+\)", "> [图片见原飞书纪要]", text)
    text = re.sub(r"https://internal-api-drive-stream\.feishu\.cn/[^\s)>\"]+", "[飞书临时下载链接已隐藏]", text)
    text = re.sub(r"https://[^)\s>\"']*authcode[^)\s>\"']*", "[飞书临时下载链接已隐藏]", text)
    text = re.sub(r"!\[[^\]]*\]\(\[飞书临时下载链接已隐藏\]\)", "> [飞书图片临时链接已隐藏，可回到原纪要查看]", text)
    text = re.sub(r'token="[A-Za-z0-9_-]+"', 'token="[已隐藏]"', text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def section(md, heading):
    pattern = rf"^#\s+{re.escape(heading)}\s*$"
    match = re.search(pattern, md, re.M)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^#\s+\S", md[start:], re.M)
    end = start + next_match.start() if next_match else len(md)
    return md[start:end].strip()


def compact_summary(md, fallback):
    summary = section(md, "Summary")
    if not summary:
        summary = md
    summary = sanitize_markdown(summary)
    summary = re.sub(r"^[-*]\s+\*\*.*?\*\*\s*$", "", summary, flags=re.M)
    lines = []
    for raw in summary.splitlines():
        line = raw.strip(" >\t")
        if not line or line.startswith("[") or line.startswith("<"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        line = re.sub(r"\*\*", "", line)
        lines.append(line)
        if len("".join(lines)) > 360:
            break
    text = " ".join(lines).strip()
    return text[:520] or fallback


def extract_chapters(md, limit=18):
    smart = section(md, "Smart chapters")
    chapters = []
    pattern = re.compile(r"\[(\d{2}:\d{2}(?::\d{2})?)\]\(([^)]+)\)\s+\*\*(.+?)\*\*(?:\n+>\s*(.+?))?(?=\n\n\[|\Z)", re.S)
    for timecode, url, title, desc in pattern.findall(smart):
        chapters.append(
            {
                "time": timecode,
                "title": re.sub(r"\s+", " ", title).strip(),
                "detail": re.sub(r"\s+", " ", desc or "").strip()[:360],
                "url": url,
            }
        )
        if len(chapters) >= limit:
            break
    return chapters


def extract_decisions(md, limit=8):
    decisions_text = sanitize_markdown(section(md, "Key decisions"))
    items = []
    for raw in decisions_text.splitlines():
        line = raw.strip()
        if not line.startswith(("-", "1.", "2.", "3.", "4.", "5.")):
            continue
        line = re.sub(r"^[-*\d.]+\s*", "", line)
        line = re.sub(r"\*\*", "", line).strip()
        if len(line) >= 12:
            items.append(line[:260])
        if len(items) >= limit:
            break
    return items


def extract_quotes(md, event_id, city, source_url, limit=3):
    quotes_text = section(md, "Notable quotes")
    found = re.findall(r"[\"“]([^\"”]{8,90})[\"”]", quotes_text)
    quotes = []
    for value in found[:limit]:
        quotes.append(
            {
                "event_id": event_id,
                "city": city,
                "quote": value.strip(),
                "theme": "会议金句",
                "note": "摘自智能纪要的 Notable quotes。",
                "source_url": source_url,
            }
        )
    return quotes


def extract_actions(md, event_id, city, source_url, limit=3):
    actions = []
    markers = ["后续工作计划", "其他决策", "待办", "行动", "计划"]
    for marker in markers:
        match = re.search(rf"{marker}(.+?)(?:\n-\s+\*\*|\n#|\Z)", md, re.S)
        if not match:
            continue
        block = sanitize_markdown(match.group(1))
        for raw in block.splitlines():
            line = raw.strip()
            if not line.startswith(("-", "1.", "2.", "3.", "4.", "5.")):
                continue
            line = re.sub(r"^[-*\d.]+\s*", "", line)
            line = re.sub(r"\*\*", "", line).strip()
            if len(line) < 12:
                continue
            actions.append(
                {
                    "event_id": event_id,
                    "city": city,
                    "owner": "相关成员",
                    "title": line.split("：", 1)[0][:28],
                    "detail": line[:300],
                    "priority": "中",
                    "source_url": source_url,
                }
            )
            if len(actions) >= limit:
                return actions
    return actions[:limit]


def classify_tags(text):
    rules = [
        ("AI", ["AI", "大模型", "Claude", "Codex", "OpenClaw", "智能"]),
        ("AI企服", ["企业服务", "企服", "B 端", "B端", "企业 AI", "企业培训"]),
        ("AI编程", ["编程", "ClaudeCode", "Claude Code", "PRD", "工具", "代码"]),
        ("跨境电商", ["跨境", "亚马逊", "出海", "电商"]),
        ("内容营销", ["内容", "营销", "私域", "公域", "成交"]),
        ("小红书", ["小红书"]),
        ("投资", ["投资", "基金", "股票", "赛道", "资产"]),
        ("播客", ["播客"]),
        ("硬件", ["硬件", "录音卡", "自动驾驶"]),
        ("社群", ["社群", "联合办公", "分享会", "圆桌"]),
    ]
    tags = []
    for tag, words in rules:
        if any(word.lower() in text.lower() for word in words):
            tags.append(tag)
    return tags or ["分享会"]


def extract_links(md):
    links = []
    seen = set()
    for label, url in re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", md):
        if "internal-api-drive-stream.feishu.cn" in url or "authcode" in url:
            continue
        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        parsed = urlparse(url)
        kind = "external"
        if "feishu.cn" in parsed.netloc and "/docx/" in parsed.path:
            kind = "feishu-docx"
        elif "feishu.cn" in parsed.netloc and "/wiki/" in parsed.path:
            kind = "feishu-wiki"
        elif "feishu.cn" in parsed.netloc and "/minutes/" in parsed.path:
            kind = "feishu-minutes"
        elif "d.biji.com" in parsed.netloc or "biji.com" in parsed.netloc:
            kind = "biji"
        links.append({"label": label.strip(), "url": url.strip(), "kind": kind})
    return links


def minute_token(url):
    parsed = urlparse(url)
    if "/minutes/" not in parsed.path:
        return ""
    return parsed.path.rstrip("/").split("/")[-1]


def link_fetch_summary(link, event_id, index):
    url = link["url"]
    kind = link["kind"]
    cache_prefix = f"guangzhou-{event_id}-{index}-{short_hash(url)}"
    if kind in {"feishu-docx", "feishu-wiki"}:
        fetched = safe_fetch_doc(url, cache_prefix)
        content = doc_content(fetched)
        if content:
            return sanitize_markdown(content)
    if kind == "feishu-minutes":
        fetched = fetch_minutes(url, cache_prefix)
        if not fetched or fetched.get("ok") is False:
            return ""
        chunks = []
        artifacts = fetched.get("data", {}).get("artifacts") or fetched.get("artifacts") or {}
        summary = artifacts.get("summary")
        if summary:
            chunks.append("### 妙记 AI 总结\n\n" + json.dumps(summary, ensure_ascii=False, indent=2))
        todos = artifacts.get("todos")
        if todos:
            chunks.append("### 妙记待办\n\n" + json.dumps(todos, ensure_ascii=False, indent=2))
        chapters = artifacts.get("chapters")
        if chapters:
            chunks.append("### 妙记章节\n\n" + json.dumps(chapters, ensure_ascii=False, indent=2))
        return sanitize_markdown("\n\n".join(chunks))
    return ""


def build_shenzhen_events():
    node_info = run_lark(
        ["wiki", "spaces", "get_node", "--as", "user", "--params", json.dumps({"token": SHENZHEN_TOKEN}, ensure_ascii=False), "--format", "json"],
        cache_name="shenzhen-root-node.json",
    )
    space_id = node_info["data"]["node"]["space_id"]
    children = run_lark(
        [
            "wiki",
            "nodes",
            "list",
            "--as",
            "user",
            "--params",
            json.dumps({"space_id": space_id, "parent_node_token": SHENZHEN_TOKEN, "page_size": 50}, ensure_ascii=False),
            "--format",
            "json",
        ],
        cache_name="shenzhen-children.json",
    )
    events = []
    all_actions = []
    all_quotes = []
    for node in children.get("data", {}).get("items", []):
        url = node.get("url") or f"https://scailabs.feishu.cn/wiki/{node['node_token']}"
        event_id = f"shenzhen-{normalize_date(node.get('title','')).replace('-', '')}-{slugify(node.get('node_token',''), short_hash(url))}"
        fetched = safe_fetch_doc(url, f"shenzhen-{node['node_token']}")
        content = sanitize_markdown(doc_content(fetched))
        date = normalize_date(node.get("title", ""))
        title = node.get("title", "")
        topic = strip_title_prefix(title)
        summary = compact_summary(content, topic)
        links = extract_links(content)
        tags = classify_tags(f"{title} {content[:2400]}")
        chapters = extract_chapters(content)
        decisions = extract_decisions(content)
        status = "full"
        if not content:
            status = "link-only"
        event = {
            "id": event_id,
            "city": "深圳",
            "date": date,
            "title": title,
            "speaker": parse_speaker_from_title(topic),
            "topic": topic,
            "source_url": url,
            "source_type": "feishu-wiki-child",
            "summary": summary,
            "notes_md": content,
            "chapters": chapters,
            "decisions": decisions,
            "links": links,
            "tags": tags,
            "status": status,
        }
        events.append(event)
        all_actions.extend(extract_actions(content, event_id, "深圳", url))
        all_quotes.extend(extract_quotes(content, event_id, "深圳", url))
        print(f"fetched Shenzhen: {title}", file=sys.stderr)
    return events, all_actions, all_quotes


def parse_speaker_from_title(title):
    pieces = re.split(r"[：:|｜]", title, maxsplit=1)
    if len(pieces) >= 2 and 1 <= len(pieces[0]) <= 16:
        return pieces[0].strip()
    return ""


def split_guangzhou_sections(index_md):
    sections = []
    matches = list(re.finditer(r"^##\s+\*\*(.+?)\*\*\s*$", index_md, re.M))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(index_md)
        sections.append((match.group(1).strip(), index_md[start:end].strip()))
    return sections


def bullet_value(section_text, label):
    match = re.search(rf"^-\s+{re.escape(label)}[：:]\s*(.+)$", section_text, re.M)
    return match.group(1).strip() if match else ""


def build_guangzhou_events():
    fetched = safe_fetch_doc(GUANGZHOU_ROOT, "guangzhou-index")
    index_md = sanitize_markdown(doc_content(fetched))
    sections = split_guangzhou_sections(index_md)
    events = []
    all_actions = []
    all_quotes = []
    for idx, (heading, body) in enumerate(sections):
        date = normalize_date(heading)
        event_id = f"guangzhou-{date.replace('-', '') or idx + 1:0>2}-{idx + 1:02d}"
        speaker = bullet_value(body, "嘉宾/分享人")
        topic = bullet_value(body, "主题/内容")
        links = extract_links(body)
        fetched_parts = []
        for link_index, link in enumerate(links):
            if link["kind"] in {"feishu-docx", "feishu-wiki", "feishu-minutes"}:
                extra = link_fetch_summary(link, event_id, link_index)
                if extra:
                    fetched_parts.append(f"## 补充资料：{link['label']}\n\n{extra}")
        combined = sanitize_markdown(body)
        if fetched_parts:
            combined = f"{combined}\n\n" + "\n\n".join(fetched_parts)
        title = heading
        summary = compact_summary(combined, f"{speaker}：{topic}" if speaker or topic else heading)
        tags = classify_tags(f"{heading} {speaker} {topic} {combined[:2000]}")
        status = "full" if fetched_parts else "index"
        event = {
            "id": event_id,
            "city": "广州",
            "date": date,
            "title": title,
            "speaker": speaker,
            "topic": topic,
            "source_url": GUANGZHOU_ROOT,
            "source_type": "feishu-wiki-index",
            "summary": summary,
            "notes_md": combined,
            "chapters": extract_chapters(combined, limit=12),
            "decisions": extract_decisions(combined, limit=6),
            "links": links,
            "tags": tags,
            "status": status,
        }
        events.append(event)
        actions = extract_actions(combined, event_id, "广州", GUANGZHOU_ROOT, limit=2)
        if not actions and topic:
            actions = [
                {
                    "event_id": event_id,
                    "city": "广州",
                    "owner": speaker or "相关成员",
                    "title": "复盘本场主题",
                    "detail": f"围绕“{topic}”整理可复用方法、案例与下一步行动。",
                    "priority": "中",
                    "source_url": GUANGZHOU_ROOT,
                }
            ]
        all_actions.extend(actions)
        all_quotes.extend(extract_quotes(combined, event_id, "广州", GUANGZHOU_ROOT, limit=2))
        print(f"fetched Guangzhou: {title}", file=sys.stderr)
    return events, all_actions, all_quotes, index_md


def event_page(event, event_actions, event_quotes):
    links = event.get("links", [])
    link_lines = "\n".join(f"- [{link['label']}]({link['url']}) `{link['kind']}`" for link in links) or "- 暂无外部链接"
    chapter_lines = "\n".join(
        f"- **{chapter['time']}** [{chapter['title']}]({chapter['url']})：{chapter.get('detail','')}"
        for chapter in event.get("chapters", [])
    ) or "- 暂无章节数据"
    decision_lines = "\n".join(f"- {item}" for item in event.get("decisions", [])) or "- 暂无结构化关键决策"
    action_lines = "\n".join(f"- **{item['title']}**：{item['detail']}" for item in event_actions) or "- 暂无自动抽取行动项"
    quote_lines = "\n".join(f"> {item['quote']}\n" for item in event_quotes) or "> 暂无自动抽取金句"
    tags = "、".join(event.get("tags", []))
    body = f"""---
title: {event['title']}
type: events
tags: {json.dumps(event.get('tags', []), ensure_ascii=False)}
updated: {datetime.now().strftime('%Y-%m-%d')}
---

# {event['title']}

> **城市：**{event['city']}  
> **日期：**{event.get('date') or '未标注'}  
> **嘉宾/分享人：**{event.get('speaker') or '未标注'}  
> **状态：**{event.get('status')}  
> **原始链接：**[{event['source_url']}]({event['source_url']})

## 一句话摘要

{event.get('summary') or '暂无摘要。'}

## 主题标签

{tags or '未标注'}

## 智能章节

{chapter_lines}

## 关键决策

{decision_lines}

## 行动项

{action_lines}

## 金句摘录

{quote_lines}

## 原始链接与资料

{link_lines}

## 公开整理纪要

{event.get('notes_md') or '该条目当前仅保留来源链接，暂未拉取到可公开整理正文。'}

## 来源边界

本页来自飞书 Wiki / Docx / 妙记 AI 产物的公开整理版。已移除飞书临时下载鉴权链接、内部文件流地址、白板 token 和原始逐字稿正文；需要查看附件、封面图或原始权限内容，请回到飞书源链接。
"""
    return body


def write_site_files(events, actions, quotes, guangzhou_index_md):
    events = sorted(events, key=lambda item: (item.get("date") or "", item.get("title") or ""), reverse=True)
    for event in events:
        event_actions = [item for item in actions if item["event_id"] == event["id"]]
        event_quotes = [item for item in quotes if item["event_id"] == event["id"]]
        write_text(ROOT / "events" / f"{event['id']}.md", event_page(event, event_actions, event_quotes))

    config = {
        "title": "生财联合办公分享会 Wiki",
        "description": "深圳与广州联合办公分享会会议纪要、资料链接、行动计划和金句墙。",
        "subtitle": "把深圳约 20 场子页面纪要与广州 14 场活动资料，整理成可搜索、可复盘、可传播、可执行的专题站。",
        "repo": "https://github.com/siuserxiaowei/scai-meeting-minutes-wiki-2026",
        "pages_url": "https://siuserxiaowei.github.io/scai-meeting-minutes-wiki-2026/",
        "shenzhen_wiki": SHENZHEN_ROOT,
        "guangzhou_wiki": GUANGZHOU_ROOT,
        "feishu_internal_doc": "",
        "modules": {
            "meeting_map": True,
            "event_pages": True,
            "action_dashboard": True,
            "quote_wall": True,
            "source_boundary": True,
        },
    }
    write_json(ROOT / "data" / "site.config.json", config)
    write_json(ROOT / "data" / "events.json", events)
    write_json(ROOT / "data" / "actions.json", actions[:120])
    write_json(ROOT / "data" / "quotes.json", quotes[:80])

    write_text(
        ROOT / "index.md",
        """---
title: Wiki Index
type: guide
tags: ["index", "overview"]
updated: 2026-05-28
---

# Wiki Index

这是一份把深圳、广州联合办公分享会资料整理成专题站的索引。

## 先读

- [[how-to-read]] — 如何阅读这份资料库
- [[meeting-overview]] — 来源、规模与组织方式
- [[sources-and-permissions]] — 资料来源与公开边界

## 分析入口

- [[meeting-map]] — 会议地图
- [[action-dashboard]] — 行动计划
- [[topic-matrix]] — 主题矩阵
- [[golden-quotes]] — 金句墙
""",
    )
    write_text(
        ROOT / "guide" / "how-to-read.md",
        """---
title: 如何阅读这份资料库
type: guide
tags: ["guide"]
updated: 2026-05-28
---

# 如何阅读这份资料库

建议按三层读：

## 先看全局

从 [[meeting-overview]] 和 [[meeting-map]] 开始，先了解深圳与广州两套来源的结构差异。

## 再看单场

深圳页面适合逐场深读；广州页面适合从活动索引进入，顺着原始链接继续看录音卡片、飞书纪要或 PPT。

## 最后看行动

进入 [[action-dashboard]]，把会议里的后续工作计划、关键决策和可复用方法拆成自己的下一步。
""",
    )
    write_text(
        ROOT / "guide" / "meeting-overview.md",
        f"""---
title: 会议总览
type: guide
tags: ["overview"]
updated: 2026-05-28
---

# 会议总览

## 来源结构

- **深圳：**[生财深圳联合办公分享会]({SHENZHEN_ROOT})，根页面下是子页面树，每个子页面基本对应一场完整智能纪要。
- **广州：**[生财联合办公广州站分享会资料合集]({GUANGZHOU_ROOT})，一个索引页列出 14 场活动，包含笔记、录音卡片、PPT、飞书纪要等链接。

## 数据规模

- 当前生成会议条目：**{len(events)}** 场。
- 当前行动项：**{len(actions[:120])}** 条。
- 当前金句：**{len(quotes[:80])}** 条。

## 公开站点定位

这个站点不是替代飞书权限系统，而是把可读纪要整理成公开复盘入口：摘要、结构化章节、行动计划、原始链接和来源边界。
""",
    )
    write_text(
        ROOT / "guide" / "sources-and-permissions.md",
        f"""---
title: 资料来源与权限说明
type: guide
tags: ["source", "permissions"]
updated: 2026-05-28
---

# 资料来源与权限说明

## 主要来源

- 深圳 Wiki：[{SHENZHEN_ROOT}]({SHENZHEN_ROOT})
- 广州 Wiki：[{GUANGZHOU_ROOT}]({GUANGZHOU_ROOT})

## 公开边界

- 已移除飞书临时下载鉴权链接、内部文件流地址、附件临时授权参数、白板标识。
- 不发布原始逐字稿正文；如某个妙记只提供逐字稿，本公开站点只保留源链接或 AI 产物摘要。
- 外部录音卡片、网盘、表单、PPT 等资源不做二次抓取，只保留原始链接和资料说明。
- 如果某条飞书链接无法读取，会标记为 `link-only` 或保留在“原始链接与资料”中。

## 广州索引原始结构摘录

以下摘录来自广州资料合集，用于说明其索引性质：

```markdown
{guangzhou_index_md[:3000]}
```
""",
    )
    write_text(
        ROOT / "analysis" / "meeting-map.md",
        """---
title: 会议地图
type: analysis
tags: ["map", "events"]
updated: 2026-05-28
---

# 会议地图

下方交互区会按城市、读取状态、标题、嘉宾和主题筛选全部会议条目。
""",
    )
    write_text(
        ROOT / "analysis" / "action-dashboard.md",
        """---
title: 行动计划
type: analysis
tags: ["actions", "plan"]
updated: 2026-05-28
---

# 行动计划

这里聚合从纪要中抽取出的后续计划、关键决策和可执行动作。建议每次只选 1-3 条推进，不要把资料库变成新的待办压力源。
""",
    )
    write_text(
        ROOT / "analysis" / "topic-matrix.md",
        """---
title: 主题矩阵
type: analysis
tags: ["topics", "matrix"]
updated: 2026-05-28
---

# 主题矩阵

```mermaid
mindmap
  root((联合办公分享会))
    AI
      AI企服
      AI编程
      AI硬件
    生意
      内容营销
      私域成交
      跨境电商
    组织
      社群
      联合办公
      两地联动
    资产
      投资
      资料库
      行动计划
```
""",
    )
    write_text(
        ROOT / "quotes" / "golden-quotes.md",
        """---
title: 金句墙
type: quotes
tags: ["quotes"]
updated: 2026-05-28
---

# 金句墙

金句来自智能纪要的 Notable quotes 或整理后的会议判断。下方卡片区适合截图传播。
""",
    )
    write_text(
        ROOT / "README.md",
        """# 生财联合办公分享会 Wiki

> 深圳与广州联合办公分享会的独立复盘站。  
> 计划发布地址：<https://siuserxiaowei.github.io/scai-meeting-minutes-wiki-2026/>

本仓库把两个飞书 Wiki 来源整理成可检索、可复盘、可传播的静态站：会议地图、单场纪要、行动计划、主题矩阵、金句墙和来源权限说明。

## 本地构建

```bash
python3 site/import_lark.py
python3 site/build.py
python3 -m http.server 8123
```

打开 <http://127.0.0.1:8123/> 预览。

## 公开边界

构建脚本会移除飞书临时下载鉴权链接、内部文件流地址、附件临时授权参数、白板标识，不发布原始逐字稿正文。
""",
    )
    write_text(
        ROOT / "SCHEMA.md",
        """# Wiki Schema

## Domain

深圳与广州联合办公分享会复盘。覆盖 AI、企服、内容营销、跨境电商、小红书、AI 编程、投资、社群和行动计划。

## Data Files

- `data/events.json`: 会议条目，字段包括 `id, city, date, title, speaker, topic, source_url, source_type, summary, notes_md, chapters, decisions, links, tags, status`。
- `data/actions.json`: 行动项，字段包括 `event_id, owner, title, detail, priority, source_url`。
- `data/quotes.json`: 金句，字段包括 `event_id, quote, theme, note`。
- `data/site.config.json`: 站点配置、来源链接和模块开关。

## Conventions

- 文件名使用小写英文和连字符。
- 页面之间使用 `[[wiki-link]]` 双向链接。
- 公开 HTML 不应包含飞书临时鉴权链接、内部文件流地址、访问凭据或原始逐字稿正文。
""",
    )
    write_text(
        ROOT / ".gitignore",
        """.DS_Store
.cache/
minutes/
*.log
""",
    )


def main():
    ensure_dirs()
    shenzhen_events, shenzhen_actions, shenzhen_quotes = build_shenzhen_events()
    guangzhou_events, guangzhou_actions, guangzhou_quotes, guangzhou_index_md = build_guangzhou_events()
    events = shenzhen_events + guangzhou_events
    actions = shenzhen_actions + guangzhou_actions
    quotes = shenzhen_quotes + guangzhou_quotes

    if not quotes:
        for event in events[:10]:
            if event.get("summary"):
                quotes.append(
                    {
                        "event_id": event["id"],
                        "city": event["city"],
                        "quote": event["summary"][:54],
                        "theme": "会议摘要",
                        "note": event["title"],
                        "source_url": event["source_url"],
                    }
                )

    write_site_files(events, actions, quotes, guangzhou_index_md)
    print(f"generated events={len(events)} actions={len(actions)} quotes={len(quotes)}")


if __name__ == "__main__":
    main()
