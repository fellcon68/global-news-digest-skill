---
name: global-news-digest
description: "Use when the user wants a daily global news digest: '生成今日/昨日全球热点新闻'、'每日新闻简报'、'全球热点 TOP10'、'新闻分类精选'、'经济/股票/科技/政治/军事 新闻汇总'. Fetches yesterday's hot news from the TOP20 official media via GDELT, classifies into 5 categories (economy/stock/tech/politics/military) with TOP10 each, renders a polished HTML page and pushes via agent-mail."
agent_created: true
version: "1.1.0"
---

# 每日全球热点新闻简要（global-news-digest）

> 方法论文脉：本技能由 obra/superpowers 方法论驱动构建。运行本技能时，请严格按以下流程执行，**不得用模型记忆冒充实时新闻**——所有新闻条目必须来自 `fetch_news.py` 实际调用的 GDELT API 返回。

## 核心纪律（红线）

1. **真实性**：新闻名称、来源机构、链接必须来自 GDELT 返回的 `title` / `domain` / `url`，**严禁编造**。
2. **实时性**：只处理 `fetch_news.py` 实际抓回的数据；"前一天"由脚本按北京时间计算。
3. **透明热度**：页面"火爆度"必须标注"含 AI 推理，非官方阅读量"。

## 运行环境与依赖

- **Python 3.8+**（脚本使用标准库 + `requests`）。
- **第三方依赖**：`requests`（仅 `fetch_news.py` 使用）。若环境中未安装，执行抓取前先运行 `pip install requests`；`render_html.py` 仅用标准库，无需额外依赖。脚本已对缺失依赖做友好提示。
- **联网说明**：抓取阶段会向 GDELT Doc 2.0 API（`api.gdeltproject.org`）发起新闻检索请求；**不上传任何用户隐私数据**，仅传出新闻检索关键词与时间窗。
- **路径约定**：所有输入输出默认落在技能目录内的 `outputs/news-digest/`，以 `<skill_dir>` 指代技能根目录，不依赖任何硬编码绝对路径，可跨机器使用。

## 执行流程（每次运行必须走完）

### ① 确定目标日期
- 默认 = **北京时间"昨天"**（脚本自动算）。
- 若用户指定日期（如"生成 2026-10-20 的新闻"），以用户指定为准，传给脚本。

### ② 抓取原始候选（实际调用 API）
```
python <skill_dir>/scripts/fetch_news.py <YYYY-MM-DD>
```
- 产出：`<skill_dir>/outputs/news-digest/<YYYY-MM-DD>.raw.news.json`
- 内容：5 个类别各自最多 40 条候选（含 `title/url/domain/seendate/language/sourcecountry/gdelt_rank`）。
- **提速要点（v1.1）**：每类「关键词 + 域名分块」直接向 GDELT 查询（受 GDELT query 长度上限 ≈300 字符约束，20 个域名需分 3–4 块/类，5 类共约 **16 次**请求，旧版 20 次）；核心修复是**把 429 退避由 15/30/45s 改为温和的 6/12/18s、并新增启动冷却 30s**，避免限流雪崩——这是缩短耗时的主要来源。正常情况下数分钟内完成。输出结构不变。
- 单类失败不中断整体；空类在结果中标 `"error"` 或空数组。

### ③ AI 后处理（你=AI 来做，产出最终结构化 JSON）
读取 `raw.news.json`，对**每个类别**执行：
- 去重（同一事件多源/近似标题合并，保留权威源）；剔除关键词命中但不相关的噪音。
- **选出 TOP10**（按显著性：GDELT 排名 + 跨媒体覆盖度 + 地缘/市场影响）。
- 为每条写**中文简要（≤60 字）**，翻译/概括原标题。
- 给每条打 **`ai_heat`（0–100）**，依据：事件重要性、影响范围、是否多源共振。
- 计算 `hotness = round(0.6 * gdelt_score + 0.4 * ai_heat)`，其中
  `gdelt_score = (N - gdelt_rank + 1) / N * 100`（N 为该类别候选总数）。
- 由 `domain` 后缀匹配得到 `source`（机构中文名，见 `references/media_list.md`）。
- 写出 `<skill_dir>/outputs/news-digest/<YYYY-MM-DD>.news.json`，结构：
```json
{
  "date": "YYYY-MM-DD",
  "generated_at": "ISO8601",
  "categories": [
    {"key":"economy","name":"经济","items":[
       {"rank":1,"title":"原标题","summary":"中文简要≤60字","source":"路透社",
        "domain":"reuters.com","hotness":87,"gdelt_rank":2,"ai_heat":90,"url":"https://..."}
    ]}
  ]
}
```
> 5 个类别 key：`economy`(经济) / `stock`(股票) / `tech`(科技) / `politics`(政治) / `military`(军事)。

### ④ 渲染 HTML
```
python <skill_dir>/scripts/render_html.py <YYYY-MM-DD>
```
- 产出：`<skill_dir>/outputs/news-digest/<YYYY-MM-DD>.html`（单文件、内联 CSS、响应式、5 类分区、每类 TOP10 表、含免责声明）。

### ⑤ 呈现 / 推送
- **手动触发**：用 `present_files` 打开 HTML 预览并交付。
- **定时自动化（需自行配置）**：如需"每日 北京时间 08:00 自动生成并推送"，请在 WorkBuddy 自动化中新建一条每日递归任务，prompt 复制本技能的执行流程（②→③→④→⑤），并在结尾调用 `agent_mail`（`mcp__agent-mail__SendMessage`，必要时先 `agent_mail_upload_attachment` 上传 HTML）向用户邮箱推送简报（正文附一句摘要 + 日期；附件为 HTML 文件）。**注意：该自动化不会随技能安装自动创建，需每个用户自行配置。**
- **前置条件**：`agent_mail` 推送需用户在连接器已配置可用邮箱与收件人；若未配置，技能会改为回报表单 HTML 绝对路径，不静默失败。

## 数据源与约束

- **主源**：GDELT Doc 2.0 API（`https://api.gdeltproject.org/api/v2/doc/doc`），免费、无需密钥。
- **域名过滤**用 `query` 内的 `domain:` 运算符（GDELT 无 `domainlist` 参数）。
- **限流**：GDELT 严格 1 次/5 秒；`fetch_news.py` 内置全局统一 7 秒节流 + 温和 429 退避（6/12/18s）重试 + 启动冷却 30s。每日约 16 次查询，远在免费额度内。
- **域名过滤**用 `query` 内的 `domain:` 运算符（GDELT 无 `domainlist` 参数）；因 query 总长上限约 300 字符，20 个媒体域名按字符预算切成约 2 块分次查询。
- **时间窗**：北京时间昨日 00:00–24:00 → 换算 UTC 作为 `startdatetime`/`enddatetime`（`YYYYMMDDHHMMSS`）。
- 详见 `references/media_list.md`（TOP20 名单与增删指引）。
