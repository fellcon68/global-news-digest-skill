# 全球热点新闻简要（global-news-digest）

> 由 obra/superpowers 方法论驱动构建。从 GDELT 聚合的 **TOP20 全球官方媒体**抓取"前一天"热点，按 **经济 / 股票 / 科技 / 政治 / 军事** 五类各筛 **TOP10**，渲染为精致 HTML 并可通过 agent-mail 推送。

## 1. 依赖

- **Python 3.8+**（脚本使用标准库 + `requests`）。
- 第三方库：`requests`（**仅 `fetch_news.py` 使用**）。未安装时运行 `pip install requests` 即可；`render_html.py` 仅用标准库，无需额外依赖。脚本已对缺失依赖做友好提示。
- 实时联网访问 GDELT Doc 2.0 API（免费、无需密钥）；不上传任何用户隐私数据。

## 2. 用法

### 手动触发
对 WorkBuddy 说，例如：
> "生成昨日全球热点新闻" / "今日新闻简报" / "经济 股票 科技 政治 军事 新闻汇总"

智能体会按 `SKILL.md` 流程执行：抓取 → AI 后处理 → 渲染 → 预览。

### 自动每日推送（需自行配置）
本技能提供"每日 北京时间 08:00 自动生成并 agent-mail 推送"的能力，但该自动化**不会随技能安装自动创建**。安装后请在 WorkBuddy 自动化中按 `SKILL.md` 第 ⑤ 步的流程自行新建每日递归任务（需 agent-mail 已配置收件人）。

## 3. 数据流与产物

```
fetch_news.py <YYYY-MM-DD>   →  outputs/news-digest/<日期>.raw.news.json   （原始候选，每类≤40）
   [AI 后处理：去重/筛选/TOP10/中文简要/ai_heat/机构映射]
                              →  outputs/news-digest/<日期>.news.json      （最终结构化）
render_html.py <YYYY-MM-DD>   →  outputs/news-digest/<日期>.html           （呈现页）
```

- 时间窗：北京时间目标日 00:00–24:00，换算 UTC 作为 GDELT 起止。
- 域名过滤：查询仅用类别关键词（短、合规），抓回后客户端按 TOP20 域名过滤。

## 4. 火爆度说明

```
hotness = round( 0.6 × gdelt_score + 0.4 × ai_heat )
gdelt_score = (N - gdelt_rank + 1) / N × 100      # N 为该类别候选总数
ai_heat    = AI（本智能体）按事件重要性打的 0–100 分
```

**页面已明确标注：含 AI 推理，非官方阅读量。** GDELT 不返回逐篇阅读量，故以"排名热度 + AI 推理"合成。

## 5. TOP20 媒体名单（均衡版）

路透社 / 美联社 / BBC / 彭博社 / CNBC / 金融时报 / 华尔街日报 / NHK / 德国之声 / 半岛电视台 / 新华社 / CGTN / 日本经济新闻 / 世界报 / 卫报 / 纽约时报 / 华盛顿邮报 / CNN / 法新社 / 南华早报(SCMP)。

**增删媒体**：编辑 `scripts/fetch_news.py` 顶部的 `TOP_MEDIA`（`(key, 中文名, 英文名, 域名)` 四元组）。域名按"后缀匹配"，子域（如 arabic.cnn.com）自动归入母媒体。详见 `references/media_list.md`。

## 6. 已知限制 / 注意

- **GDELT 限流严格**（约 1 次/5 秒）。脚本已内置 6 秒间隔 + 429 退避；每日 5 次查询在免费额度内。共享 IP 高频场景可能偶发 429，单类失败不中断整体。
- **需实时联网**：新闻来自 API，绝不使用模型记忆。
- **空态**：某类当日无相关报道时，页面显示"暂无数据"而非报错。
- **NewsAPI 增强（可选）**：如需更干净的中文源，可在 `fetch_news.py` 增加 NewsAPI 适配层（需 API key），当前未启用。

## 7. 文件结构

```
global-news-digest/
├── SKILL.md                 # 入口与流程编排
├── _skillhub_meta.json      # 技能展示名（本地）
├── README.md                # 本文件
├── references/media_list.md # TOP20 名单与增删指引
├── scripts/
│   ├── fetch_news.py        # 抓取层（GDELT）
│   └── render_html.py       # 渲染层（HTML）
└── outputs/news-digest/     # 生成产物（.raw.news.json / .news.json / .html）
```
