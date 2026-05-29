#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "index.html"
PAGE_DIRS = ["guide", "events", "analysis", "quotes"]


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text.strip()
    _, meta_text, body = text.split("---", 2)
    meta = {}
    for raw in meta_text.strip().splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            try:
                value = json.loads(value.replace("'", '"'))
            except json.JSONDecodeError:
                value = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        meta[key.strip()] = value
    return meta, body.strip()


def collect_pages():
    pages = []
    files = [ROOT / "index.md"]
    for page_dir in PAGE_DIRS:
        files.extend(sorted((ROOT / page_dir).glob("*.md")))

    for path in files:
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        route = "home-index" if path.name == "index.md" else path.stem
        group = meta.get("type") or (path.parent.name if path.parent != ROOT else "guide")
        pages.append(
            {
                "route": route,
                "path": str(path.relative_to(ROOT)),
                "title": meta.get("title") or path.stem,
                "group": group,
                "tags": meta.get("tags", []),
                "body": body,
                "updated": meta.get("updated", ""),
            }
        )
    return pages


def counter(items, key):
    return Counter(item.get(key, "未标注") for item in items if item.get(key))


def tag_counter(events):
    counts = Counter()
    for event in events:
        for tag in event.get("tags", []):
            counts[tag] += 1
    return counts


def build():
    config = read_json("data/site.config.json")
    events = read_json("data/events.json")
    actions = read_json("data/actions.json")
    quotes = read_json("data/quotes.json")
    pages = collect_pages()

    groups = [
        {"id": "guide", "label": "导览"},
        {"id": "events", "label": "会议纪要"},
        {"id": "analysis", "label": "行动与分析"},
        {"id": "quotes", "label": "金句传播"},
    ]

    payload = {
        "config": config,
        "pages": pages,
        "events": events,
        "actions": actions,
        "quotes": quotes,
        "groups": groups,
        "cityCounts": counter(events, "city"),
        "statusCounts": counter(events, "status"),
        "tagCounts": tag_counter(events),
        "builtAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    html = TEMPLATE
    for key, value in {
        "__TITLE__": config["title"],
        "__DESCRIPTION__": config["description"],
        "__PAYLOAD__": json.dumps(payload, ensure_ascii=False),
    }.items():
        html = html.replace(key, value)

    OUT.write_text(html, encoding="utf-8")
    print(f"built {OUT}")
    print(f"pages={len(pages)} events={len(events)} actions={len(actions)} quotes={len(quotes)}")


TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__</title>
<meta name="description" content="__DESCRIPTION__" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600;700&family=Noto+Sans+SC:wght@400;500;700;800;900&family=Noto+Serif+SC:wght@700;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
:root{
  --bg:#101210;
  --panel:#171b17;
  --panel-2:#20261f;
  --ink:#f5f0dc;
  --muted:#aaa58e;
  --line:rgba(245,240,220,.16);
  --green:#a9d46e;
  --teal:#70d0c3;
  --gold:#f2bd52;
  --red:#e66e62;
  --blue:#88b9ff;
  --paper:#efe5c5;
  --black:#0d0f0d;
  --shadow:0 24px 70px rgba(0,0,0,.34);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;
  min-height:100vh;
  color:var(--ink);
  background:
    linear-gradient(rgba(245,240,220,.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(245,240,220,.028) 1px, transparent 1px),
    linear-gradient(180deg,#10130f 0%,#141711 54%,#0d0f0c 100%);
  background-size:36px 36px,36px 36px,100% 100%;
  font-family:"Noto Sans SC",system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  letter-spacing:0;
}
a{color:inherit}
button,input,select{font:inherit}
.layout{display:grid;grid-template-columns:322px minmax(0,1fr);min-height:100vh}
.sidebar{
  position:sticky;
  top:0;
  height:100vh;
  overflow:auto;
  padding:22px 18px;
  border-right:1px solid var(--line);
  background:rgba(12,15,12,.94);
  backdrop-filter:blur(18px);
  z-index:20;
}
.brand{display:grid;gap:10px;margin-bottom:18px}
.brand-mark{
  width:44px;height:44px;border-radius:8px;
  background:linear-gradient(135deg,var(--gold),var(--green) 54%,var(--teal));
  display:grid;place-items:center;color:#10120f;font-weight:900;
  box-shadow:0 0 0 1px rgba(255,255,255,.18),0 18px 40px rgba(0,0,0,.24);
}
.brand h1{margin:0;font-size:20px;line-height:1.2;font-weight:900}
.brand p{margin:0;color:var(--muted);font-size:13px;line-height:1.7}
.search{
  width:100%;height:44px;border-radius:8px;border:1px solid var(--line);
  background:#0d100d;color:var(--ink);padding:0 12px;outline:none;
}
.search:focus{border-color:rgba(169,212,110,.75);box-shadow:0 0 0 3px rgba(169,212,110,.13)}
.quick{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0 18px}
.quick a,.nav a{text-decoration:none;color:var(--muted);border:1px solid transparent}
.quick a{padding:10px 12px;border-radius:8px;background:rgba(255,255,255,.035);font-size:13px;color:var(--ink)}
.quick a:hover,.nav a:hover{border-color:var(--line);color:var(--ink);background:rgba(255,255,255,.04)}
.group{margin:18px 0}
.group-title{
  color:var(--gold);
  font:700 12px/1 "IBM Plex Mono",monospace;
  text-transform:uppercase;
  letter-spacing:0;
  margin:0 0 8px;
}
.nav{display:grid;gap:3px}
.nav a{
  display:block;padding:8px 10px;border-radius:7px;font-size:14px;line-height:1.35;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.nav a.active{color:#11140f;background:var(--green);border-color:transparent;font-weight:800}
.nav .path{display:block;color:rgba(245,240,220,.45);font-size:11px;margin-top:2px;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.content{min-width:0}
.topbar{
  position:sticky;top:0;z-index:10;height:60px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:0 28px;border-bottom:1px solid var(--line);
  background:rgba(16,18,15,.78);backdrop-filter:blur(18px);
}
.crumb{color:var(--muted);font-size:13px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.built{color:rgba(245,240,220,.54);font:600 12px/1 "IBM Plex Mono",monospace;white-space:nowrap}
.menu{display:none;width:42px;height:42px;border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.04);color:var(--ink)}
.main{max-width:1220px;margin:0 auto;padding:34px 28px 80px}
.hero{
  min-height:calc(100vh - 108px);
  display:grid;align-content:center;gap:26px;
  padding:22px 0 42px;
}
.eyebrow{
  display:inline-flex;align-items:center;gap:8px;color:#10120f;background:var(--gold);
  width:max-content;border-radius:999px;padding:8px 12px;font-weight:900;font-size:12px;
}
.hero h2{
  margin:0;
  font-family:"Noto Serif SC",serif;
  font-size:clamp(42px,7vw,90px);
  line-height:1.04;
  letter-spacing:0;
  max-width:1080px;
}
.hero-lead{max-width:850px;color:#d6d0b5;font-size:19px;line-height:1.9;margin:0}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.metric{
  min-height:126px;border:1px solid var(--line);border-radius:8px;padding:18px;
  background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.025));
  box-shadow:var(--shadow);
}
.metric strong{display:block;font:800 32px/1.05 "IBM Plex Mono",monospace;color:var(--green);margin-bottom:10px;overflow-wrap:anywhere}
.metric span{color:var(--muted);font-size:14px;line-height:1.55}
.section{margin:44px 0}
.section h3,.article h1{
  font-family:"Noto Serif SC",serif;
  font-size:34px;
  margin:0 0 18px;
  letter-spacing:0;
}
.section-intro{color:var(--muted);line-height:1.8;max-width:860px}
.insight-grid,.event-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.insight,.event-card,.action-card,.panel{
  border:1px solid var(--line);border-radius:8px;background:rgba(23,27,23,.82);
  box-shadow:var(--shadow);
  min-width:0;overflow-wrap:anywhere;
}
.insight{padding:18px}
.insight h4{margin:0 0 8px;font-size:18px}
.insight p{margin:0;color:#d2ccb0;line-height:1.75}
.visual-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}
.panel{padding:18px}
.panel h4{margin:0 0 14px;font-size:18px}
.bars{display:grid;gap:10px}
.bar-row{display:grid;grid-template-columns:132px minmax(0,1fr) 38px;gap:10px;align-items:center}
.bar-label{color:#ded8bd;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-track{height:12px;border-radius:999px;background:rgba(255,255,255,.08);overflow:hidden}
.bar-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--green),var(--teal))}
.bar-num{text-align:right;color:var(--gold);font:700 13px/1 "IBM Plex Mono",monospace}
.tools{display:grid;grid-template-columns:minmax(0,1fr) 150px 180px;gap:10px;margin-bottom:16px}
.tools input,.tools select{
  height:42px;border-radius:8px;border:1px solid var(--line);background:#10130f;color:var(--ink);padding:0 12px;min-width:0;
}
.event-card{
  display:grid;gap:12px;text-decoration:none;padding:16px;min-height:300px;
}
.event-card:hover{border-color:rgba(169,212,110,.7);background:rgba(169,212,110,.07)}
.event-card time{font:800 13px/1 "IBM Plex Mono",monospace;color:var(--gold)}
.event-card h4{margin:0;font-size:18px;line-height:1.42}
.event-summary{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.event-counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.event-counts span{border:1px solid var(--line);border-radius:7px;padding:7px 6px;color:#d8d1b8;font-size:12px;text-align:center;background:rgba(255,255,255,.035)}
.meta{display:flex;flex-wrap:wrap;gap:6px}
.pill{border-radius:999px;padding:5px 8px;background:rgba(112,208,195,.12);color:#aee9df;font-size:12px}
.pill.gold{background:rgba(242,189,82,.14);color:#f4d28b}
.event-card p,.action-card p{margin:0;color:#d4ceb3;line-height:1.65;font-size:14px}
.action-board{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.action-card{padding:16px;min-height:180px}
.action-card time{font:800 12px/1 "IBM Plex Mono",monospace;color:var(--gold)}
.action-card h4{margin:10px 0 8px;font-size:17px}
.action-lanes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}
.action-lane{border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.035);padding:14px;min-width:0;overflow-wrap:anywhere}
.action-lane h4{margin:0 0 12px;color:var(--gold)}
.action-lane ol{margin:0;padding-left:20px;color:#d8d1b8;line-height:1.75}
.action-lane li{margin:0 0 8px}
.quote-wall{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.quote-card{
  min-height:250px;border-radius:8px;border:1px solid rgba(242,189,82,.36);
  background:linear-gradient(145deg,rgba(242,189,82,.16),rgba(112,208,195,.07)),rgba(255,255,255,.04);
  padding:22px;display:grid;align-content:space-between;gap:18px;
  min-width:0;overflow-wrap:anywhere;
}
.quote-card blockquote{margin:0;font-family:"Noto Serif SC",serif;font-size:25px;line-height:1.32;font-weight:900;overflow-wrap:anywhere}
.quote-card .tag{color:var(--gold);font-weight:800;font-size:13px}
.quote-card p{margin:8px 0 0;color:#c9c2a7;line-height:1.55;font-size:13px}
.article{
  max-width:920px;
  border:1px solid var(--line);
  border-radius:8px;
  background:rgba(23,27,23,.8);
  padding:34px;
  box-shadow:var(--shadow);
  overflow-wrap:anywhere;
}
.article h1{font-size:38px}
.article h2{font-size:25px;margin:34px 0 12px;border-top:1px solid var(--line);padding-top:22px}
.article h3{font-size:20px;margin:26px 0 10px}
.article p,.article li{color:#d8d1b8;line-height:1.86;font-size:16px}
.article blockquote{margin:18px 0;padding:14px 18px;border-left:4px solid var(--green);background:rgba(169,212,110,.08);color:#eee8ce}
.article table{width:100%;border-collapse:collapse;margin:18px 0;font-size:14px}
.article th,.article td{border:1px solid var(--line);padding:10px;vertical-align:top}
.article th{background:rgba(255,255,255,.06);color:var(--gold);text-align:left}
.article code{font-family:"IBM Plex Mono",monospace;background:rgba(255,255,255,.08);padding:2px 5px;border-radius:4px}
.article pre{overflow:auto;background:#0b0d0b;border:1px solid var(--line);border-radius:8px;padding:16px}
.article a{color:#bde987;text-decoration:none;border-bottom:1px solid rgba(189,233,135,.35);overflow-wrap:anywhere;word-break:break-word}
.article img{max-width:100%;height:auto;border-radius:8px}
.empty{padding:24px;color:var(--muted);border:1px dashed var(--line);border-radius:8px}
.scrim{display:none}
@media (min-width:981px) and (max-width:1380px){
  .quote-wall,.action-board,.action-lanes{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width:980px){
  html,body{overflow-x:hidden}
  .layout{display:block}
  .sidebar{position:fixed;left:0;top:0;transform:translateX(-104%);transition:transform .22s ease;width:min(86vw,340px);max-width:100vw;overflow-x:hidden;contain:layout paint}
  .sidebar.open{transform:translateX(0)}
  .scrim.open{display:block;position:fixed;inset:0;background:rgba(0,0,0,.48);z-index:15}
  .menu{display:grid;place-items:center}
  .topbar{padding:0 14px}
  .main{padding:24px 16px 64px}
  .metric-grid,.insight-grid,.event-grid,.visual-grid,.action-board,.quote-wall{grid-template-columns:1fr}
  .action-lanes{grid-template-columns:1fr}
  .event-counts{grid-template-columns:repeat(2,minmax(0,1fr))}
  .tools{grid-template-columns:1fr}
  .hero{min-height:auto;padding-top:20px}
  .hero h2{font-size:clamp(38px,14vw,62px)}
  .article{padding:22px;max-width:100%;min-width:0}
  .article h1{font-size:30px}
  .article h2{font-size:22px}
  .nav a,.nav .path{max-width:100%;min-width:0;overflow:hidden;text-overflow:ellipsis}
}
</style>
</head>
<body>
<div class="scrim" id="scrim"></div>
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <div class="brand">
      <div class="brand-mark">M</div>
      <h1>会议纪要 Wiki</h1>
      <p>深圳与广州联合办公分享会的公开复盘站。按会议、主题、行动项和金句组织。</p>
    </div>
    <input class="search" id="search" placeholder="搜索会议、嘉宾、主题..." />
    <div class="quick">
      <a href="#home">总览</a>
      <a href="#meeting-map">会议地图</a>
      <a href="#action-dashboard">行动计划</a>
      <a href="#golden-quotes">金句墙</a>
    </div>
    <div id="nav"></div>
  </aside>
  <main class="content">
    <header class="topbar">
      <button class="menu" id="mobileMenu" aria-label="打开菜单">☰</button>
      <div class="crumb" id="crumb">会议洞察总览</div>
      <div class="built" id="built"></div>
    </header>
    <div class="main" id="app"></div>
  </main>
</div>
<script>
const DATA = __PAYLOAD__;
const {config, pages, events, actions, quotes, groups, cityCounts, statusCounts, tagCounts} = DATA;
const byRoute = Object.fromEntries(pages.map(page => [page.route, page]));
const byEvent = Object.fromEntries(events.map(event => [event.id, event]));
const actionsByEvent = actions.reduce((acc, item) => {
  (acc[item.event_id] ||= []).push(item);
  return acc;
}, {});
const quotesByEvent = quotes.reduce((acc, item) => {
  (acc[item.event_id] ||= []).push(item);
  return acc;
}, {});
const nav = document.getElementById('nav');
const app = document.getElementById('app');
const crumb = document.getElementById('crumb');
const search = document.getElementById('search');
const sidebar = document.getElementById('sidebar');
const scrim = document.getElementById('scrim');
const mobileMenu = document.getElementById('mobileMenu');
document.getElementById('built').textContent = DATA.builtAt;

mermaid.initialize({startOnLoad:false, theme:'dark', securityLevel:'loose'});
marked.use({
  renderer: {
    link(href, title, text) {
      const clean = String(href || '');
      const label = text || clean;
      if (clean.startsWith('#')) return `<a href="${clean}">${label}</a>`;
      return `<a href="${clean}" target="_blank" rel="noreferrer">${label}</a>`;
    }
  }
});

function pageLink(route, label){
  return `<a href="#${route}">${label}</a>`;
}

function normalizeWikiLinks(md){
  return String(md || '').replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (_, route, label) => `[${label}](#${route})`)
    .replace(/\[\[([^\]]+)\]\]/g, (_, route) => `[${route}](#${route})`);
}

function markdown(md){
  return marked.parse(normalizeWikiLinks(md || ''));
}

function pageGroup(page){
  if (['guide','events','analysis','quotes'].includes(page.group)) return page.group;
  if (page.path.startsWith('events/')) return 'events';
  return 'guide';
}

function renderNav(filter=''){
  const q = filter.trim().toLowerCase();
  const visible = pages.filter(page => {
    if (page.route === 'home-index') return true;
    const hay = `${page.title} ${page.path} ${(page.tags||[]).join(' ')} ${page.body}`.toLowerCase();
    return !q || hay.includes(q);
  });
  nav.innerHTML = groups.map(group => {
    const items = visible.filter(page => pageGroup(page) === group.id);
    if (!items.length) return '';
    return `<section class="group"><h2 class="group-title">${group.label}</h2><div class="nav">${items.map(page =>
      `<a href="#${page.route}" data-route="${page.route}"><span>${page.title}</span><span class="path">${page.path}</span></a>`
    ).join('')}</div></section>`;
  }).join('');
  markActive();
}

function markActive(){
  const route = location.hash.replace(/^#/, '') || 'home';
  document.querySelectorAll('.nav a').forEach(a => a.classList.toggle('active', a.dataset.route === route));
}

function barChart(counter){
  const entries = Object.entries(counter).sort((a,b)=>b[1]-a[1]);
  const max = Math.max(...entries.map(([,v])=>v), 1);
  return `<div class="bars">${entries.map(([label,value])=>`
    <div class="bar-row"><div class="bar-label" title="${label}">${label}</div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(8, value/max*100)}%"></div></div><div class="bar-num">${value}</div></div>
  `).join('')}</div>`;
}

function eventCard(event){
  const tags = (event.tags || []).slice(0, 4).map(tag => `<span class="pill">${tag}</span>`).join('');
  const firstTakeaway = (event.key_takeaways || [])[0] || event.summary || event.topic || '查看详情';
  const counts = {
    章节: (event.chapters || []).length,
    角色: (event.roles || []).length,
    行动: (actionsByEvent[event.id] || []).length,
    观点: (quotesByEvent[event.id] || []).length
  };
  return `<a class="event-card" href="#${event.id}">
    <div>
      <time>${event.date || '未标日期'} · ${event.city}</time>
      <h4>${event.title}</h4>
      <div class="meta"><span class="pill gold">${event.status}</span>${tags}</div>
    </div>
    <p><strong>嘉宾：</strong>${event.speaker || '未标注'}</p>
    <p class="event-summary"><strong>可带走：</strong>${firstTakeaway}</p>
    <div class="event-counts">${Object.entries(counts).map(([label,value])=>`<span>${value}<br>${label}</span>`).join('')}</div>
  </a>`;
}

function quoteCard(q){
  const event = byEvent[q.event_id] || {};
  return `<article class="quote-card"><blockquote>${q.quote || ''}</blockquote><div><div class="tag">${q.theme || '观点卡'}</div><p>${q.note || ''}</p>${q.event_id ? `<p><a href="#${q.event_id}">查看来源：${event.title || q.event_id}</a></p>` : ''}</div></article>`;
}

function globalInsights(){
  return [
    ['不要把会议当素材库', '每场会都先抽出“判断、角色、章节、行动、观点卡”，读者可以先拿结论，再回到原始纪要核对。'],
    ['AI 企服是最密集主线', '培训、案例库、工具、陪跑、自动化交付反复出现，关键不只是会 AI，而是能帮客户降本、增效或成交。'],
    ['项目诊断要看角色', '广州场里大量价值藏在“谁在做什么、卡在哪里、被建议怎么改”，所以单场页新增关键角色与项目拆解。'],
    ['行动要足够具体', '行动计划从 64 条扩展为更细的验证、获客、定价、招聘、内容、交付动作，并按优先级和主题聚合。'],
    ['观点卡要承担传播', '金句墙不再只取少量 Notable quotes，也抽取会议里的判断句，适合快速复盘和截图转发。'],
    ['原文是证据，不是首页', '完整整理稿保留在单场底部，用来核对上下文；页面上半部分负责帮读者学习和行动。']
  ];
}

function renderHome(){
  crumb.textContent = '会议洞察总览';
  const readable = events.filter(e => e.status !== 'link-only').length;
  const latest = [...events].filter(e => e.date).sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0, 6);
  const chapterTotal = events.reduce((sum,event)=>sum + (event.chapters || []).length, 0);
  const roleTotal = events.reduce((sum,event)=>sum + (event.roles || []).length, 0);
  const highActions = actions.filter(item => item.priority === '高').slice(0, 6);
  app.innerHTML = `
    <section class="hero">
      <div class="eyebrow">SCAI Meeting Wiki 2026</div>
      <h2>把 34 场创业复盘，拆成可学习、可执行的知识库。</h2>
      <p class="hero-lead">${config.subtitle}</p>
      <div class="metric-grid">
        <div class="metric"><strong>${events.length}</strong><span>会议与活动条目，覆盖深圳子页面与广州资料合集</span></div>
        <div class="metric"><strong>${chapterTotal}</strong><span>智能章节，按时间线回到具体讨论点</span></div>
        <div class="metric"><strong>${roleTotal}</strong><span>关键角色与项目卡点，尤其适合看项目诊断</span></div>
        <div class="metric"><strong>${actions.length}</strong><span>行动项，覆盖获客、定价、交付、招聘、内容和调研</span></div>
      </div>
    </section>
    <section class="section">
      <h3>先看六个判断</h3>
      <div class="insight-grid">
        ${globalInsights().map(([title,detail])=>`<article class="insight"><h4>${title}</h4><p>${detail}</p></article>`).join('')}
      </div>
    </section>
    <section class="section">
      <h3>7 天优先行动</h3>
      <p class="section-intro">先从高优先级里选一条验证，不要把资料库变成新的收藏压力。</p>
      <div class="action-board">${highActions.map(action => `
        <article class="action-card">
          <time>${action.priority || '中'} · ${action.city || ''} · ${action.theme || ''}</time>
          <h4>${action.title || action.owner || '行动项'}</h4>
          <p><strong>${action.owner || '相关成员'}</strong><br>${action.detail || ''}</p>
        </article>
      `).join('')}</div>
    </section>
    <section class="section visual-grid">
      <div class="panel"><h4>城市分布</h4>${barChart(cityCounts)}</div>
      <div class="panel"><h4>主题密度</h4>${barChart(tagCounts)}</div>
    </section>
    <section class="section">
      <h3>最近会议</h3>
      <div class="event-grid">${latest.map(eventCard).join('')}</div>
    </section>
    <section class="section">
      <h3>传播摘录</h3>
      <div class="quote-wall">${quotes.slice(0, 6).map(quoteCard).join('')}</div>
    </section>
  `;
}

function renderMeetingMap(){
  return `<section class="section">
    <h3>会议地图</h3>
    <p class="section-intro">按城市、状态、主题、嘉宾和标题筛选。每张卡片都显示章节、角色、行动和观点卡数量，点进去先看二次整理，再看完整整理稿。</p>
    <div class="tools">
      <input id="eventFilter" placeholder="筛选标题、嘉宾、主题、标签..." />
      <select id="cityFilter"><option value="">全部城市</option>${Object.keys(cityCounts).map(s=>`<option>${s}</option>`).join('')}</select>
      <select id="statusFilter"><option value="">全部状态</option>${Object.keys(statusCounts).map(s=>`<option>${s}</option>`).join('')}</select>
    </div>
    <div class="event-grid" id="eventGrid">${events.map(eventCard).join('')}</div>
  </section>
  <section class="section visual-grid">
    <div class="panel"><h4>城市分布</h4>${barChart(cityCounts)}</div>
    <div class="panel"><h4>读取状态</h4>${barChart(statusCounts)}</div>
  </section>`;
}

function wireMeetingMap(){
  const q = document.getElementById('eventFilter');
  const city = document.getElementById('cityFilter');
  const status = document.getElementById('statusFilter');
  const grid = document.getElementById('eventGrid');
  if (!q || !city || !status || !grid) return;
  const refresh = () => {
    const keyword = q.value.trim().toLowerCase();
    const items = events.filter(event => {
      const hay = `${event.title} ${event.speaker} ${event.topic} ${event.summary} ${(event.tags||[]).join(' ')} ${(event.key_takeaways||[]).join(' ')} ${(event.roles||[]).map(role=>`${role.name} ${role.role} ${role.advice}`).join(' ')}`.toLowerCase();
      return (!keyword || hay.includes(keyword)) && (!city.value || event.city === city.value) && (!status.value || event.status === status.value);
    });
    grid.innerHTML = items.length ? items.map(eventCard).join('') : '<div class="empty">没有匹配的会议。换一个关键词试试。</div>';
  };
  [q, city, status].forEach(el => el.addEventListener('input', refresh));
}

function renderActionDashboard(){
  const byPriority = ['高','中','低'].map(priority => [priority, actions.filter(item => (item.priority || '中') === priority).slice(0, 10)]);
  const byTheme = actions.reduce((acc,item) => {
    const key = item.theme || '其他';
    (acc[key] ||= []).push(item);
    return acc;
  }, {});
  const themeBlocks = Object.entries(byTheme).sort((a,b)=>b[1].length-a[1].length).slice(0, 6);
  return `<section class="section">
    <h3>行动计划</h3>
    <p class="section-intro">行动项来自待办、项目建议、关键决策和章节判断。先看高优先级，再按主题回到对应会议页读上下文。</p>
    <div class="action-lanes">${byPriority.map(([priority,items]) => `
      <div class="action-lane">
        <h4>${priority}优先级 · ${actions.filter(item => (item.priority || '中') === priority).length} 条</h4>
        <ol>${items.map(item => `<li><a href="#${item.event_id}">${item.title}</a>：${item.detail}</li>`).join('')}</ol>
      </div>
    `).join('')}</div>
  </section>
  <section class="section">
    <h3>按主题推进</h3>
    <div class="insight-grid">${themeBlocks.map(([theme,items])=>`
      <article class="insight"><h4>${theme} · ${items.length} 条</h4><p>${items.slice(0,4).map(item=>`${item.title}：${item.detail}`).join('；')}</p></article>
    `).join('')}</div>
  </section>
  <section class="section">
    <h3>全部行动项</h3>
    <div class="action-board">${actions.map(action => `
      <article class="action-card">
        <time>${action.priority || '中'} · ${action.city || ''} · ${action.theme || ''}</time>
        <h4>${action.title || action.owner || '行动项'}</h4>
        <p><strong>${action.owner || '相关成员'}</strong><br>${action.detail || ''}</p>
        <p><a href="#${action.event_id}">回到来源会议</a></p>
      </article>
    `).join('')}</div>
  </section>`;
}

function renderQuoteWall(){
  return `<section class="section">
    <h3>金句墙</h3>
    <p class="section-intro">短句适合截图传播；每张卡片都保留主题和来源事件入口。</p>
    <div class="quote-wall">${quotes.map(quoteCard).join('')}</div>
  </section>`;
}

async function renderPage(route){
  const page = byRoute[route];
  if (!page) {
    if (route === 'home') return renderHome();
    app.innerHTML = '<div class="empty">页面不存在。</div>';
    crumb.textContent = 'Not found';
    return;
  }
  crumb.textContent = page.title;
  let extra = '';
  if (route === 'meeting-map') extra = renderMeetingMap();
  if (route === 'action-dashboard') extra = renderActionDashboard();
  if (route === 'golden-quotes') extra = renderQuoteWall();
  app.innerHTML = `<article class="article">${markdown(page.body)}</article>${extra}`;
  wireMeetingMap();
  await renderMermaid();
}

async function renderMermaid(){
  const blocks = [...document.querySelectorAll('code.language-mermaid')];
  for (let i = 0; i < blocks.length; i++) {
    const code = blocks[i];
    const holder = document.createElement('div');
    holder.className = 'mermaid';
    holder.textContent = code.textContent;
    code.closest('pre').replaceWith(holder);
  }
  if (document.querySelector('.mermaid')) await mermaid.run({querySelector:'.mermaid'});
}

function navigate(){
  closeMenu();
  const route = location.hash.replace(/^#/, '') || 'home';
  markActive();
  if (route === 'home') renderHome();
  else renderPage(route);
}

function openMenu(){ sidebar.classList.add('open'); scrim.classList.add('open'); }
function closeMenu(){ sidebar.classList.remove('open'); scrim.classList.remove('open'); }

search.addEventListener('input', () => renderNav(search.value));
mobileMenu.addEventListener('click', openMenu);
scrim.addEventListener('click', closeMenu);
window.addEventListener('hashchange', navigate);
renderNav();
navigate();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    build()
