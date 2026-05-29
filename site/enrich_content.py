#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


THEME_RULES = [
    ("AI企服", ["企业服务", "企服", "B端", "B 端", "企业 AI", "企业培训", "陪跑", "交付"]),
    ("AI编程", ["编程", "代码", "Claude", "Codex", "PRD", "小程序", "APP", "应用开发"]),
    ("流量增长", ["流量", "获客", "公域", "私域", "涨粉", "投放", "搜索", "自然流"]),
    ("内容IP", ["内容", "IP", "自媒体", "公众号", "小红书", "短视频", "视频号", "推特", "TikTok", "TK"]),
    ("成交变现", ["成交", "变现", "定价", "收钱", "客户", "高客单", "订单", "收入", "利润"]),
    ("跨境电商", ["跨境", "亚马逊", "出海", "POD", "电商", "店铺", "选品"]),
    ("投资赛道", ["投资", "基金", "股票", "赛道", "资产", "龙头", "指数"]),
    ("组织协作", ["社群", "联合办公", "招聘", "合伙", "团队", "资源", "合作"]),
]

GENERIC_HEADINGS = {
    "项目分享与交流",
    "后续工作计划",
    "总结",
    "智能章节",
    "待办",
    "关键决策",
    "其他决策",
    "AI 车库的起源与意义",
    "AI车库的起源与意义",
}


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write_json(name, data):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_text(value, limit=None):
    text = value or ""
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"</?[^>]+>", "", text)
    text = text.strip()
    text = re.sub(r"^[-*]\s+\[[ xX]\]\s*", "", text)
    text = re.sub(r"^\[[ xX]\]\s*", "", text)
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"^\d+[.)]\s*", "", text)
    text = re.sub(r"\*\*|__|`|>", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ：:，,。;；")
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip("，,；;、 ") + "…"
    return text


def split_sentences(text):
    cleaned = clean_text(text)
    parts = re.split(r"(?<=[。！？!?])\s*|[；;]\s*", cleaned)
    return [p.strip(" ，,。") for p in parts if len(p.strip()) >= 12]


def section(md, names):
    if isinstance(names, str):
        names = [names]
    headings = [re.escape(name) for name in names]
    pattern = rf"^#{{1,3}}\s+(?:{'|'.join(headings)})\s*$"
    match = re.search(pattern, md or "", re.M)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^#{1,3}\s+\S", md[start:], re.M)
    end = start + next_match.start() if next_match else len(md)
    return md[start:end].strip()


def summary_block(md):
    return section(md, ["Summary", "总结", "妙记 AI 总结", "妙记AI总结"]) or md or ""


def infer_theme(text, tags=None):
    source = f"{' '.join(tags or [])} {text}"
    for theme, words in THEME_RULES:
        if any(word.lower() in source.lower() for word in words):
            return theme
    return (tags or ["会议观点"])[0]


def classify_more_tags(text, existing):
    tags = list(dict.fromkeys(existing or []))
    for tag, words in THEME_RULES:
        if tag not in tags and any(word.lower() in text.lower() for word in words):
            tags.append(tag)
    return tags[:10] or ["创业复盘"]


def outline_cards(md, event, limit=10):
    block = summary_block(md)
    lines = block.splitlines()
    cards = []
    current = None
    for raw in lines:
        line = raw.rstrip()
        match = re.match(r"^\s*-\s+\*\*([^*\n]{2,40})\*\*\s*$", line)
        if match:
            if current and current["details"]:
                cards.append(current)
            current = {"title": clean_text(match.group(1), 36), "details": []}
            continue
        if current and re.search(r"^\s*-\s+", line):
            detail = clean_text(line, 210)
            if detail and detail != current["title"] and detail not in current["details"]:
                current["details"].append(detail)
        if len(cards) >= limit:
            break
    if current and current["details"] and len(cards) < limit:
        cards.append(current)

    if not cards:
        sentences = split_sentences(block)
        for idx, sentence in enumerate(sentences[:limit]):
            title = event.get("topic") or event.get("title") or f"判断 {idx + 1}"
            cards.append({"title": clean_text(title, 34), "details": [sentence]})

    insights = []
    for card in cards[:limit]:
        detail = "；".join(card["details"][:3])
        if len(detail) < 12:
            continue
        insights.append(
            {
                "title": card["title"],
                "detail": clean_text(detail, 360),
                "theme": infer_theme(f"{card['title']} {detail}", event.get("tags")),
            }
        )
    return insights


def parse_chapters(md, existing=None, limit=36):
    chapters = list(existing or [])
    seen = {(c.get("time"), c.get("title")) for c in chapters}
    block = section(md, ["Smart chapters", "智能章节", "妙记章节"])
    pattern = re.compile(
        r"\[(\d{2}:\d{2}(?::\d{2})?)\]\((https?://[^)]+)\)\s+\*\*(.+?)\*\*(?:\n+>\s*(.+?))?(?=\n\n\[|\n#|\Z)",
        re.S,
    )
    for timecode, url, title, desc in pattern.findall(block):
        key = (timecode, clean_text(title, 80))
        if key in seen:
            continue
        chapters.append(
            {
                "time": timecode,
                "title": clean_text(title, 90),
                "detail": clean_text(desc, 420),
                "url": url,
            }
        )
        seen.add(key)
        if len(chapters) >= limit:
            break
    return chapters[:limit]


def parse_roles(md, event, insights, limit=18):
    block = summary_block(md)
    lines = block.splitlines()
    candidates = []
    for idx, raw in enumerate(lines):
        match = re.match(r"^(\s*)-\s+\*\*([^*\n]{1,32})\*\*\s*$", raw)
        if not match:
            continue
        name = clean_text(match.group(2), 28)
        if not name or name in GENERIC_HEADINGS or len(name) > 18:
            continue
        window = "\n".join(lines[idx + 1 : idx + 9])
        if not re.search(r"项目介绍|业务介绍|介绍自己|介绍自身|分享自身|目前有.{0,20}项目", window):
            continue
        project = ""
        advice = ""
        for item in re.findall(r"^\s*-\s+(.+)$", window, re.M):
            item_text = clean_text(item, 260)
            if not project and re.search(r"项目介绍|业务介绍|从事|目前|做了|想做|计划", item_text):
                project = re.sub(r"^(项目介绍|业务介绍)[：:]\s*", "", item_text)
            if not advice and re.match(r"^(建议|涛哥建议|后续建议|解决方案|卡点建议)[：:]", item_text):
                advice = re.sub(r"^(建议|涛哥建议|后续建议|解决方案|卡点建议)[：:]\s*", "", item_text)
        if project or advice:
            candidates.append({"name": name, "role": project or "项目/观点分享者", "advice": advice})

    speaker = event.get("speaker")
    if speaker and not candidates and not any(item["name"] == speaker for item in candidates):
        candidates.insert(
            0,
            {
                "name": speaker,
                "role": event.get("topic") or event.get("title") or "主讲人",
                "advice": insights[0]["detail"] if insights else event.get("summary", ""),
            },
        )
    return candidates[:limit]


def parse_decisions(md, event, insights, existing=None, limit=14):
    items = []
    seen = set()
    for value in existing or []:
        text = clean_text(value, 260)
        if text and text not in seen:
            items.append(text)
            seen.add(text)

    blocks = [
        section(md, ["Key decisions", "关键决策", "其他决策"]),
        section(md, ["后续工作计划", "待办"]),
        summary_block(md),
    ]
    for block in blocks:
        for raw in block.splitlines():
            line = clean_text(raw, 260)
            if len(line) < 14 or line in seen:
                continue
            if not re.search(r"建议|强调|认为|应|需要|可以|不要|优先|核心|关键|重点|计划|目标", line):
                continue
            items.append(line)
            seen.add(line)
            if len(items) >= limit:
                return items

    for insight in insights:
        line = clean_text(f"{insight['title']}：{insight['detail']}", 260)
        if line and line not in seen:
            items.append(line)
            seen.add(line)
        if len(items) >= limit:
            break
    return items[:limit]


def quote_candidates(md, event, insights, decisions, limit=9):
    found = []
    explicit = "\n".join(
        [
            section(md, ["Notable quotes", "金句", "金句摘录"]),
            section(md, ["会议金句", "精彩观点"]),
        ]
    )
    for value in re.findall(r"[\"“]([^\"”]{8,120})[\"”]", explicit):
        found.append(clean_text(value, 96))

    source_lines = []
    source_lines.extend(decisions)
    source_lines.extend(insight["detail"] for insight in insights)
    source_lines.extend(split_sentences(summary_block(md))[:80])
    for line in source_lines:
        for sentence in split_sentences(line):
            sentence = clean_text(sentence, 96)
            if not 16 <= len(sentence) <= 96:
                continue
            if not re.search(r"核心|关键|本质|不要|先|必须|应该|适合|最好|值得|能|会|要|可|重点", sentence):
                continue
            found.append(sentence)

    quotes = []
    seen = set()
    for value in found:
        if not value or value in seen:
            continue
        seen.add(value)
        quotes.append(
            {
                "event_id": event["id"],
                "city": event["city"],
                "quote": value,
                "theme": infer_theme(value, event.get("tags")),
                "note": f"{event.get('date') or '未标日期'} · {event.get('speaker') or event.get('topic') or event.get('title')}",
                "source_url": event["source_url"],
            }
        )
        if len(quotes) >= limit:
            break
    return quotes


def priority_for(text):
    if re.search(r"成交|客户|收入|定价|MVP|跑通|试|验证|招聘|发布|获客|增长|交付|订单|利润", text):
        return "高"
    if re.search(r"整理|调研|学习|关注|复盘|分析|准备", text):
        return "中"
    return "中"


def action_title(text, fallback):
    cleaned = clean_text(text, 80)
    if "：" in cleaned:
        return clean_text(cleaned.split("：", 1)[0], 30)
    if "，" in cleaned:
        return clean_text(cleaned.split("，", 1)[0], 30)
    return clean_text(cleaned, 30) or fallback


def parse_actions(md, event, roles, decisions, limit=14):
    actions = []
    seen = set()

    def add(owner, detail, title=None):
        detail = clean_text(detail, 320)
        if len(detail) < 12 or detail in seen:
            return
        seen.add(detail)
        actions.append(
            {
                "event_id": event["id"],
                "city": event["city"],
                "owner": clean_text(owner, 24) or "相关成员",
                "title": title or action_title(detail, "推进下一步"),
                "detail": detail,
                "priority": priority_for(detail),
                "theme": infer_theme(detail, event.get("tags")),
                "event_title": event.get("title"),
                "event_date": event.get("date"),
                "source_url": event["source_url"],
            }
        )

    for block in [section(md, ["待办", "后续工作计划", "行动项"]), section(md, ["Key decisions", "关键决策"])]:
        for raw in block.splitlines():
            line = clean_text(raw, 320)
            if re.match(r"^\s*$", line) or len(line) < 12:
                continue
            if "无关键决策" in line or "本次会议为分享类会议" in line:
                continue
            if re.search(r"资料|查询|分析|尝试|制定|整理|分享|招聘|改名|验证|推进|建立|关注|学习|提升|跑通|发布|准备", line):
                add("相关成员", line)
            if len(actions) >= limit:
                return actions

    for role in roles:
        if role.get("advice"):
            add(role["name"], role["advice"], f"{role['name']}下一步")
        if len(actions) >= limit:
            return actions

    for decision in decisions:
        if re.search(r"建议|计划|应|需要|可以|优先", decision):
            add(event.get("speaker") or "相关成员", decision)
        if len(actions) >= limit:
            return actions

    return actions[:limit]


def build_summary(event, insights, roles):
    topic = event.get("topic") or event.get("title")
    if insights:
        names = "、".join(item["title"] for item in insights[:3])
        first = insights[0]["detail"]
        return clean_text(f"本场围绕“{topic}”展开，重点拆解 {names}。最值得先带走的是：{first}", 420)
    if roles:
        names = "、".join(role["name"] for role in roles[:5])
        return clean_text(f"本场围绕“{topic}”做项目交流，涉及 {names} 等角色的业务卡点与下一步建议。", 300)
    return clean_text(event.get("summary") or topic or event.get("title"), 420)


def role_lines(roles):
    if not roles:
        return "- 暂无结构化角色；可阅读下方完整整理稿。"
    lines = []
    for role in roles:
        detail = role.get("role") or "角色未标注"
        advice = f" 建议：{role['advice']}" if role.get("advice") else ""
        lines.append(f"- **{role['name']}**：{detail}{advice}")
    return "\n".join(lines)


def insight_lines(insights):
    if not insights:
        return "- 暂无结构化判断；可阅读下方完整整理稿。"
    return "\n\n".join(f"### {idx + 1}. {item['title']}\n\n{item['detail']}" for idx, item in enumerate(insights[:8]))


def chapter_lines(chapters):
    if not chapters:
        return "- 暂无章节数据；优先阅读“完整整理稿”。"
    return "\n".join(
        f"- **{item.get('time') or '时间未标'}** [{item.get('title')}]({item.get('url') or '#'})：{item.get('detail') or ''}"
        for item in chapters[:28]
    )


def action_lines(actions):
    if not actions:
        return "- 暂无自动抽取行动项。"
    return "\n".join(
        f"- **{item.get('priority', '中')}｜{item.get('owner') or '相关成员'}｜{item.get('title')}**：{item.get('detail')}"
        for item in actions
    )


def quote_lines(quotes):
    if not quotes:
        return "> 暂无自动抽取观点句。"
    return "\n\n".join(f"> {item['quote']}\n>\n> — {item.get('theme') or '会议观点'}" for item in quotes)


def links_lines(event):
    links = event.get("links") or []
    if not links:
        return f"- [{event['source_url']}]({event['source_url']}) `source`"
    return "\n".join(f"- [{link['label']}]({link['url']}) `{link.get('kind', 'external')}`" for link in links)


def event_page(event, event_actions, event_quotes):
    tags = "、".join(event.get("tags") or [])
    takeaways = event.get("key_takeaways") or []
    takeaway_lines = "\n".join(f"- {item}" for item in takeaways[:5]) or "- 先读核心判断，再按章节回到原始纪要核对上下文。"
    raw = event.get("notes_md") or "该条目当前仅保留来源链接，暂未拉取到可公开整理正文。"
    return f"""---
title: {event['title']}
type: events
tags: {json.dumps(event.get('tags', []), ensure_ascii=False)}
updated: {datetime.now().strftime('%Y-%m-%d')}
---

# {event['title']}

> 城市：{event['city']}  
> 日期：{event.get('date') or '未标注'}  
> 嘉宾/分享人：{event.get('speaker') or '未标注'}  
> 状态：{event.get('status')}  
> 原始链接：[{event['source_url']}]({event['source_url']})

## 如果只读 10 分钟

{takeaway_lines}

## 一句话摘要

{event.get('summary') or '暂无摘要。'}

## 本场最值得带走的判断

{insight_lines(event.get('insights') or [])}

## 关键角色与项目

{role_lines(event.get('roles') or [])}

## 主题标签

{tags or '未标注'}

## 智能章节

{chapter_lines(event.get('chapters') or [])}

## 行动计划

{action_lines(event_actions)}

## 金句与观点卡

{quote_lines(event_quotes)}

## 原始链接与资料

{links_lines(event)}

## 完整整理稿（用于核对）

{raw}

## 来源边界

本页来自飞书 Wiki / Docx / 妙记 AI 产物的公开整理版。已移除飞书临时下载鉴权链接、内部文件流地址、白板 token 和原始逐字稿正文；需要查看附件、封面图或原始权限内容，请回到飞书源链接。
"""


def write_support_pages(events, actions, quotes):
    tag_counts = Counter(tag for event in events for tag in event.get("tags", []))
    city_counts = Counter(event.get("city", "未标注") for event in events)
    high_actions = sum(1 for item in actions if item.get("priority") == "高")
    role_count = sum(len(event.get("roles", [])) for event in events)
    chapter_count = sum(len(event.get("chapters", [])) for event in events)

    write_text(
        ROOT / "index.md",
        """---
title: Wiki Index
type: guide
tags: ["index", "overview"]
updated: 2026-05-29
---

# Wiki Index

这不是飞书资料的搬运目录，而是一份把深圳、广州联合办公分享会拆成“判断、角色、章节、行动、观点句”的创业复盘库。

## 先读

- [[how-to-read]] — 如何从这份资料里学东西
- [[meeting-overview]] — 来源、规模与内容密度
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
title: 如何从这份资料里学东西
type: guide
tags: ["guide"]
updated: 2026-05-29
---

# 如何从这份资料里学东西

## 先读“如果只读 10 分钟”

每场会议先给 3-5 条可带走判断，避免一上来陷入原始纪要。

## 再看关键角色

项目诊断类会议最重要的不是谁说了什么，而是谁在做什么业务、卡在哪里、现场给了什么建议。

## 最后转成行动

行动计划页把会议里的待办、建议、验证动作统一拉出来。建议一次只选 1-3 条，用 7 天验证，而不是把整站当收藏夹。
""",
    )
    write_text(
        ROOT / "guide" / "meeting-overview.md",
        f"""---
title: 会议总览
type: guide
tags: ["overview"]
updated: 2026-05-29
---

# 会议总览

## 数据规模

- 会议与活动：**{len(events)}** 场。
- 城市分布：{", ".join(f"{k} {v} 场" for k, v in city_counts.items())}。
- 结构化章节：**{chapter_count}** 段。
- 关键角色/项目：**{role_count}** 个。
- 行动项：**{len(actions)}** 条，其中高优先级 **{high_actions}** 条。
- 金句与观点卡：**{len(quotes)}** 条。

## 主题密度

{", ".join(f"{tag} {count}" for tag, count in tag_counts.most_common(12))}

## 公开站点定位

公开站点承担“学习入口”和“复盘入口”：先给结构化判断和行动建议，再保留完整整理稿用于核对。飞书内部文档仍是完整资料与权限入口。
""",
    )
    write_text(
        ROOT / "analysis" / "action-dashboard.md",
        """---
title: 行动计划
type: analysis
tags: ["actions", "plan"]
updated: 2026-05-29
---

# 行动计划

这里不再只堆待办，而是把会议里出现的建议拆成可执行动作：先找高优先级，再回到对应会议页看上下文。
""",
    )
    write_text(
        ROOT / "analysis" / "meeting-map.md",
        """---
title: 会议地图
type: analysis
tags: ["map", "events"]
updated: 2026-05-29
---

# 会议地图

每张会议卡都会显示摘要、主题、章节数、角色数、行动项和观点卡数量。点进单场后先读二次整理，再看完整整理稿。
""",
    )
    write_text(
        ROOT / "analysis" / "topic-matrix.md",
        """---
title: 主题矩阵
type: analysis
tags: ["topics", "matrix"]
updated: 2026-05-29
---

# 主题矩阵

```mermaid
mindmap
  root((联合办公分享会))
    AI生意
      AI企服
      AI编程
      AI硬件
      企业培训
    增长成交
      流量增长
      内容IP
      私域承接
      高客单成交
    电商出海
      跨境电商
      小红书电商
      视频号带货
      选品与供应链
    组织资产
      社群
      联合办公
      招聘协作
      投资赛道
```
""",
    )
    write_text(
        ROOT / "quotes" / "golden-quotes.md",
        """---
title: 金句墙
type: quotes
tags: ["quotes"]
updated: 2026-05-29
---

# 金句墙

这里既包含原始纪要里的金句，也包含从会议总结中抽出的“观点卡”。它们的用途是让你快速抓住判断，而不是替代完整上下文。
""",
    )


def main():
    events = read_json("data/events.json")
    all_actions = []
    all_quotes = []
    enriched = []

    for event in events:
        md = event.get("notes_md") or ""
        event["tags"] = classify_more_tags(f"{event.get('title')} {event.get('topic')} {md[:5000]}", event.get("tags", []))
        insights = outline_cards(md, event, limit=10)
        roles = parse_roles(md, event, insights)
        chapters = parse_chapters(md, event.get("chapters", []), limit=36)
        decisions = parse_decisions(md, event, insights, event.get("decisions", []), limit=14)
        event["insights"] = insights
        event["roles"] = roles
        event["chapters"] = chapters
        event["decisions"] = decisions
        event["summary"] = build_summary(event, insights, roles)
        event["key_takeaways"] = [clean_text(f"{item['title']}：{item['detail']}", 180) for item in insights[:5]]
        event["content_score"] = min(100, 20 + len(insights) * 6 + len(roles) * 3 + len(chapters) * 2 + len(decisions) * 2)

        event_actions = parse_actions(md, event, roles, decisions, limit=14)
        event_quotes = quote_candidates(md, event, insights, decisions, limit=9)
        all_actions.extend(event_actions)
        all_quotes.extend(event_quotes)
        enriched.append(event)

    enriched = sorted(enriched, key=lambda item: (item.get("date") or "", item.get("title") or ""), reverse=True)
    all_actions = all_actions[:360]
    all_quotes = all_quotes[:260]

    for event in enriched:
        event_actions = [item for item in all_actions if item["event_id"] == event["id"]]
        event_quotes = [item for item in all_quotes if item["event_id"] == event["id"]]
        write_text(ROOT / "events" / f"{event['id']}.md", event_page(event, event_actions, event_quotes))

    config = read_json("data/site.config.json")
    config.update(
        {
            "title": "生财联合办公分享会深度 Wiki",
            "description": "深圳与广州联合办公分享会的深度复盘、关键角色、智能章节、行动计划和观点卡。",
            "subtitle": "把 34 场联合办公分享会拆成可学习、可复盘、可执行的创业知识库：先看判断，再看角色和章节，最后转成 7 天行动。",
        }
    )
    write_json("data/site.config.json", config)
    write_json("data/events.json", enriched)
    write_json("data/actions.json", all_actions)
    write_json("data/quotes.json", all_quotes)
    write_support_pages(enriched, all_actions, all_quotes)
    print(f"enriched events={len(enriched)} actions={len(all_actions)} quotes={len(all_quotes)}")


if __name__ == "__main__":
    main()
