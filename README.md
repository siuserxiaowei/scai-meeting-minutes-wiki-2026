# 生财联合办公分享会 Wiki

> 深圳与广州联合办公分享会的独立复盘站。  
> 计划发布地址：<https://siuserxiaowei.github.io/scai-meeting-minutes-wiki-2026/>
> 飞书内部索引：<https://vi8r050ecuz.feishu.cn/docx/ZWjLdfp5koixFkxWOdQcKirLndc>

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
