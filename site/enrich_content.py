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
    source = text or ""
    for theme, words in THEME_RULES:
        if any(word.lower() in source.lower() for word in words):
            return theme
    for theme, _ in THEME_RULES:
        if theme in (tags or []):
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
        if re.search(r"无关键决策|本次会议为分享类会议|AI-generated|智能纪要由 AI", value):
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


def event_mode(event):
    tags = set(event.get("tags") or [])
    role_count = len(event.get("roles") or [])
    text = f"{event.get('title','')} {event.get('topic','')} {event.get('summary','')}"
    if role_count >= 3 or re.search(r"诊断|问诊|项目交流|破冰|私董", text):
        return "项目诊断"
    if "投资" in tags or "投资赛道" in tags or re.search(r"投资|赛道|基金|股票|龙头", text):
        return "赛道判断"
    if "AI编程" in tags or re.search(r"编程|App|小程序|代码|网站", text):
        return "产品实操"
    if "成交变现" in tags or "流量增长" in tags:
        return "增长变现"
    return "创业复盘"


def data_points(md, limit=8):
    found = []
    patterns = [
        r"[^。；\n]{0,24}\d+(?:\.\d+)?\s*(?:万|亿|千|%|人|单|天|年|月|小时|分钟|个|次|元|美金|美元)[^。；\n]{0,36}",
        r"[^。；\n]{0,24}[一二三四五六七八九十]+(?:个|种|类|层|步|年|月|天)[^。；\n]{0,36}",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, md or ""):
            item = clean_text(match, 120)
            if re.search(r"录音时间|智能纪要|GMT|周[一二三四五六日天]", item):
                continue
            if item and item not in found:
                found.append(item)
            if len(found) >= limit:
                return found
    return found


def choose_tools(event, actions):
    text = " ".join(
        [
            event.get("title", ""),
            event.get("topic", ""),
            event.get("summary", ""),
            " ".join(event.get("tags") or []),
            " ".join(item.get("detail", "") for item in actions[:8]),
        ]
    )
    rules = [
        ("飞书多维表格 / 案例库", ["飞书", "多维表格", "案例库", "知识库"]),
        ("高质量 PPT / 物料包", ["PPT", "五合一", "资料", "物料"]),
        ("小红书 / 公众号 / 视频号", ["小红书", "公众号", "视频号", "自媒体"]),
        ("AI 编程与网站工具", ["编程", "代码", "网站", "App", "小程序", "工具"]),
        ("AI 生图 / 自动回复 / 工作流", ["生图", "自动回复", "工作流", "自动化"]),
        ("地推 / 混群 / 私域", ["地推", "混群", "私域", "社群"]),
        ("指数基金 / 龙头公司清单", ["指数", "基金", "股票", "龙头"]),
        ("成交路径表 / 客户访谈表", ["成交", "客户", "转化", "定价"]),
    ]
    tools = []
    for name, words in rules:
        if any(word.lower() in text.lower() for word in words):
            tools.append(name)
    return tools[:6] or ["资料库复盘表", "7 天验证清单", "客户问题清单"]


def learning_intro(event, actions):
    mode = event_mode(event)
    tags = "、".join((event.get("tags") or [])[:5])
    topic = event.get("topic") or event.get("title")
    first = (event.get("key_takeaways") or [event.get("summary", "")])[0]
    if mode == "项目诊断":
        return (
            f"这篇的学习价值不在于记住所有人的发言，而是学一套“项目问诊”的拆法：先看每个人的业务模型，再看卡点究竟在流量、成交、交付、定价还是组织，最后把建议改写成 7 天内能验证的动作。\n\n"
            f"你可以把它当成一张创业体检表。读的时候重点看三件事：第一，已有资源能不能复用；第二，赚钱对象是否足够具体；第三，下一步动作是否足够接近成交。本文覆盖的高频主题是：{tags}。\n\n"
            f"本场最先值得带走的一句话是：{first}"
        )
    if mode == "赛道判断":
        return (
            f"这篇适合用来训练“赛道判断”。它讨论的不是某个单点机会，而是如何判断一个方向是否值得长期投入：赛道是否足够大、你和龙头企业是什么关系、上中下游谁先赚钱、个人应该做投资人、创业者还是生态伙伴。\n\n"
            f"读完以后，你应该能得到一张判断清单：哪些方向值得研究，哪些只是热闹；哪些动作是认知型动作，哪些动作是执行型动作。主题关键词是：{tags}。\n\n"
            f"本场最先值得带走的一句话是：{first}"
        )
    if mode == "产品实操":
        return (
            f"这篇适合当成产品实操复盘读。不要只看“用了什么工具”，而要看从需求、开发、测试、发布、获客到变现的链路有没有闭环。\n\n"
            f"读的时候把每个判断都翻译成自己的 SOP：我怎么找需求、怎么做第一个版本、怎么验收、怎么上线、怎么拿到第一批用户。主题关键词是：{tags}。\n\n"
            f"本场最先值得带走的一句话是：{first}"
        )
    if mode == "增长变现":
        return (
            f"这篇适合训练增长和变现视角。重点不是“内容怎么写”，而是谁是明确客户、哪个渠道能带来信任、前端内容如何承接到后端产品、怎么定价和成交。\n\n"
            f"读的时候把所有建议拆成四类：获客、信任、产品、成交。只要其中一环不清楚，项目就会变成热闹但不赚钱。主题关键词是：{tags}。\n\n"
            f"本场最先值得带走的一句话是：{first}"
        )
    return (
        f"这篇适合当成创业复盘读。不要只读摘要，而要把它拆成“为什么值得做、具体怎么做、靠什么工具放大、下一步怎么验证”。\n\n"
        f"本文主题是“{topic}”，高频关键词是：{tags}。读完以后最重要的不是收藏，而是选一个动作在 7 天内验证。\n\n"
        f"本场最先值得带走的一句话是：{first}"
    )


def framework_table(event, actions):
    insights = event.get("insights") or []
    roles = event.get("roles") or []
    tools = choose_tools(event, actions)
    mode = event_mode(event)
    dao = {
        "项目诊断": "项目不是缺想法，而是缺一条足够靠近成交的验证路径。",
        "赛道判断": "先判断赛道和龙头，再判断自己是投资、创业、加入还是做生态伙伴。",
        "产品实操": "AI 降低开发门槛后，真正的壁垒变成需求判断、验收和分发。",
        "增长变现": "内容只有接到明确客户、产品和成交路径上，才会变成生意。",
        "创业复盘": "复盘的价值是把别人走过的路拆成自己能执行的动作。",
    }[mode]
    fa = insights[0]["detail"] if insights else event.get("summary", "")
    shu_source = actions[0]["detail"] if actions else (insights[1]["detail"] if len(insights) > 1 else "先把本场观点改写成自己的 7 天验证清单。")
    qi = "；".join(tools[:4])
    rows = [
        ("道", dao, f"读完先问：这件事为什么值得做？我的项目是不是也卡在同一个底层问题上？"),
        ("法", fa, "把这个判断改成自己的判断清单，不要直接照抄结论。"),
        ("术", shu_source, "选一个最小动作，在 7 天内验证，而不是继续收集资料。"),
        ("器", qi, "把工具当放大器，不要把工具当商业模式本身。"),
    ]
    return "\n".join(f"| {level} | {clean_text(content, 220)} | {clean_text(use, 160)} |" for level, content, use in rows)


def seven_field_card(event, actions, quotes):
    roles = event.get("roles") or []
    insights = event.get("insights") or []
    points = data_points(event.get("notes_md", ""), limit=5)
    tools = choose_tools(event, actions)
    mode = event_mode(event)
    guest = event.get("speaker") or (roles[0]["name"] if roles else "未标注")
    real_case = roles[0]["role"] if roles else (insights[0]["detail"] if insights else event.get("summary", ""))
    result = "；".join(points[:3]) if points else "原纪要未给出明确量化结果，重点看方法和行动路径。"
    story = roles[1]["role"] if len(roles) > 1 else (insights[1]["detail"] if len(insights) > 1 else event.get("summary", ""))
    method = insights[0]["detail"] if insights else event.get("summary", "")
    quote = quotes[0]["quote"] if quotes else (event.get("key_takeaways") or [""])[0]
    rows = [
        ("1. 嘉宾/场景", f"{guest} · {event.get('city')} · {event.get('date') or '未标日期'}。这是一场{mode}型内容，主题是：{event.get('topic') or event.get('title')}。"),
        ("2. 真实问题", clean_text(real_case, 220)),
        ("3. 关键结果/数据", clean_text(result, 220)),
        ("4. 核心故事", clean_text(story, 220)),
        ("5. 方法框架", clean_text(method, 260)),
        ("6. 工具/抓手", "；".join(tools[:5])),
        ("7. 可复用金句", clean_text(quote, 180)),
    ]
    return "\n".join(f"- **{name}**：{value}" for name, value in rows)


def method_cards(event):
    insights = (event.get("insights") or [])[:6]
    if not insights:
        return "- 暂无足够方法卡；先阅读完整整理稿。"
    lines = []
    for idx, item in enumerate(insights, 1):
        theme = infer_theme(f"{item['title']} {item['detail']}", [])
        detail = item["detail"]
        apply = "把它改写成一个可观察指标，再找一个低成本场景试一次。"
        if theme == "AI企服":
            apply = "先选一个具体行业客户，列出他们每天重复、耗人、影响成交的 3 个流程，再设计一个演示案例。"
        elif theme == "流量增长":
            apply = "先找 10 个同行爆款，拆标题、承接页和成交入口，然后用自己的案例重写一版。"
        elif theme == "成交变现":
            apply = "把客户从看到你到付费的路径画出来，每个节点只优化一个最可控动作。"
        elif theme == "跨境电商":
            apply = "先拆选品、素材、上架、履约、复购五个环节，找到最短能产生订单的验证链路。"
        elif theme == "投资赛道":
            apply = "用赛道规模、龙头位置、上下游利润、个人角色四个问题重评自己的方向。"
        elif theme == "AI编程":
            apply = "把需求写成 PRD，用 AI 做第一版，再用截图、报错和用户反馈逼近可用版本。"
        lines.append(f"### 方法 {idx}：{item['title']}\n\n- **核心意思**：{detail}\n- **你可以怎么用**：{apply}\n- **不要误读成**：看懂观点就算学会；真正的学习是把它变成一次验证。")
    return "\n\n".join(lines)


def seven_day_homework(event, actions):
    mode = event_mode(event)
    base = [item["detail"] for item in actions[:7]]
    defaults = {
        "项目诊断": [
            "把自己的项目写成一页纸：客户是谁、卖什么、为什么现在买、在哪里成交。",
            "列出当前最卡的一环：流量、信任、产品、定价、交付、团队，只选一个。",
            "找 5 个真实客户或同行案例，记录他们真实付费的理由。",
            "做一个最小销售物料：案例页、报价页、演示视频或私域话术。",
            "用 1 个渠道测试获客，不换渠道，只记录咨询数和有效对话数。",
            "复盘成交链路，把掉线最多的一步改掉。",
            "决定继续、暂停还是换打法，并写下证据。"
        ],
        "赛道判断": [
            "列出你关注的 3 个赛道，写出每个赛道的上游、中游、下游。",
            "找每个赛道的 3 家龙头，判断它们靠什么赚钱。",
            "写清楚你和龙头的关系：加入、投资、服务、做生态、还是避开。",
            "用 10 年视角问：这个方向十年后还存在吗？谁会赚最大利润？",
            "找 3 个已经在这个方向赚到钱的人，记录他们的共同点。",
            "选择一个最小参与方式：内容、服务、工具、渠道、投资观察清单。",
            "写下不做的理由，避免只因为热闹就入场。"
        ],
        "产品实操": [
            "从真实抱怨里挑一个需求，不从自己的灵感开始。",
            "写 8 行 PRD：用户、场景、痛点、输入、输出、边界、验收、推广。",
            "用 AI 做第一个可演示版本，不追求完整。",
            "找 3 个目标用户试用，记录他们卡住的位置。",
            "修一个最影响使用的缺陷。",
            "做一个发布页或演示帖，测试是否有人愿意留下联系方式。",
            "复盘：这个产品值得继续做，还是只值得沉淀成经验。"
        ],
        "增长变现": [
            "写清楚赚钱对象，不写泛泛人群。",
            "拆 10 个同行案例，记录他们怎么吸引、信任、成交。",
            "做 3 条内容，只服务一个成交目标。",
            "设计一个承接入口：私信、表单、群、咨询、资料包。",
            "给产品定一个明确价格或试用条件。",
            "找 10 个潜在客户对话，记录真实异议。",
            "复盘哪句话、哪个案例、哪个承诺最接近成交。"
        ],
        "创业复盘": [
            "把本篇 3 个判断抄到自己的项目旁边，逐条判断是否适用。",
            "挑一个最像自己的案例，写出相同点和不同点。",
            "列出一个可以本周做的小动作。",
            "找一个外部反馈来源，不靠自己想。",
            "完成一次小验证，并记录结果。",
            "根据结果改下一步，不新增大计划。",
            "写一段复盘：我学到的不是观点，而是什么行动会变。"
        ],
    }[mode]
    merged = []
    for item in base:
        cleaned = clean_text(item, 150)
        if cleaned and cleaned not in merged:
            merged.append(cleaned)
    for item in defaults:
        if item not in merged:
            merged.append(item)
    return "\n".join(f"- **Day {idx}**：{item}" for idx, item in enumerate(merged[:7], 1))


def reflection_questions(event):
    mode = event_mode(event)
    common = [
        "我现在做的事，最像本篇里的哪个案例？相同点和不同点分别是什么？",
        "这篇里哪一个判断如果是真的，会直接改变我下一步动作？",
        "我有没有把“工具能力”误当成“商业模式”？",
        "我能不能用 1 周时间验证一个最小动作，而不是继续研究？",
    ]
    extra = {
        "项目诊断": [
            "我的客户是谁？他为什么现在必须解决这个问题？",
            "我的项目卡在流量、信任、产品、定价、交付、团队中的哪一环？",
            "我有哪些资源其实可以复用，但一直没有明确对外表达？",
            "如果只能做一个销售物料，我应该做案例页、报价页还是演示视频？",
        ],
        "赛道判断": [
            "这个赛道 10 年后还会存在吗？利润会集中在哪一层？",
            "我是更适合投资、加入龙头、做生态服务，还是自己创业？",
            "我现在的认知是来自一线赚钱者，还是来自正确但无用的旁观观点？",
            "如果龙头拿走大部分利润，我能分到哪一小块？",
        ],
        "产品实操": [
            "这个需求来自真实用户，还是来自我的想象？",
            "我有没有明确验收标准，而不是只让 AI 一直改？",
            "上线后第一个用户从哪里来？",
            "我准备靠什么持续分发，而不是只发一次朋友圈？",
        ],
        "增长变现": [
            "内容后面承接的产品是什么？价格是多少？",
            "客户为什么信我，而不是信同行？",
            "我最短的成交路径有几步？哪一步损耗最大？",
            "我是在做影响力，还是在做可收钱的信任？",
        ],
        "创业复盘": [
            "这篇里的哪条经验可以变成我的 SOP？",
            "我能不能找到一个真实人群，而不是泛泛方向？",
            "我现在应该加速、收缩，还是换验证方式？",
            "我下一次复盘时，应该拿什么结果来判断进展？",
        ],
    }[mode]
    return "\n".join(f"- {item}" for item in (common + extra))


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

## 这篇真正能学什么

{learning_intro(event, event_actions)}

## 道法术器拆解

| 层 | 本场对应内容 | 你可以怎么用 |
|---|---|---|
{framework_table(event, event_actions)}

## 7 字段学习卡

{seven_field_card(event, event_actions, event_quotes)}

## 可直接复用的方法

{method_cards(event)}

## 7 天作业

{seven_day_homework(event, event_actions)}

## 回到自己业务的追问

{reflection_questions(event)}

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
