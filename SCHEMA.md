# Wiki Schema

## Domain

深圳与广州联合办公分享会复盘。覆盖 AI、企服、内容营销、跨境电商、小红书、AI 编程、投资、社群和行动计划。

## Data Files

- `data/events.json`: 会议条目，字段包括 `id, city, date, title, speaker, topic, source_url, source_type, summary, notes_md, chapters, decisions, links, tags, status, insights, roles, key_takeaways, content_score`。
- `data/actions.json`: 行动项，字段包括 `event_id, owner, title, detail, priority, theme, event_title, event_date, source_url`。
- `data/quotes.json`: 金句与观点卡，字段包括 `event_id, quote, theme, note, source_url`。
- `data/site.config.json`: 站点配置、来源链接和模块开关。

## Conventions

- 文件名使用小写英文和连字符。
- 页面之间使用 `[[wiki-link]]` 双向链接。
- 公开 HTML 不应包含飞书临时鉴权链接、内部文件流地址、访问凭据或原始逐字稿正文。
