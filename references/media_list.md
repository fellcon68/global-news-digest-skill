# TOP20 全球知名官方媒体白名单

> 用途：固化在 `scripts/fetch_news.py` 的 `TOP_MEDIA` 常量中。GDELT `domain:` 过滤按"域名后缀"匹配（含子域，如 arabic.cnn.com 也算 CNN）。
> 版本：均衡版（2026-10-25 确认）。将「经济学人」替换为「南华早报 SCMP」，增强亚洲/多极视角。

| # | 机构（中文） | 机构（英文） | 域名 | 国家/地区 |
|---|------------|------------|------|----------|
| 1 | 路透社 | Reuters | reuters.com | 英国/国际 |
| 2 | 美联社 | Associated Press | apnews.com | 美国 |
| 3 | 英国广播公司 | BBC | bbc.com | 英国 |
| 4 | 彭博社 | Bloomberg | bloomberg.com | 美国 |
| 5 | 消费者新闻与商业频道 | CNBC | cnbc.com | 美国 |
| 6 | 金融时报 | Financial Times | ft.com | 英国 |
| 7 | 华尔街日报 | The Wall Street Journal | wsj.com | 美国 |
| 8 | 日本放送协会 | NHK | nhk.or.jp | 日本 |
| 9 | 德国之声 | Deutsche Welle | dw.com | 德国 |
| 10 | 半岛电视台 | Al Jazeera | aljazeera.com | 卡塔尔 |
| 11 | 新华社 | Xinhua | xinhuanet.com | 中国 |
| 12 | 中国国际电视台 | CGTN | cgtn.com | 中国 |
| 13 | 日本经济新闻 | Nikkei | nikkei.com | 日本 |
| 14 | 世界报 | Le Monde | lemonde.fr | 法国 |
| 15 | 卫报 | The Guardian | theguardian.com | 英国 |
| 16 | 纽约时报 | The New York Times | nytimes.com | 美国 |
| 17 | 华盛顿邮报 | The Washington Post | washingtonpost.com | 美国 |
| 18 | 美国有线电视新闻网 | CNN | cnn.com | 美国 |
| 19 | 法新社 | Agence France-Presse | afp.com | 法国 |
| 20 | 南华早报 | South China Morning Post | scmp.com | 中国香港 |

## 增删指引

编辑 `scripts/fetch_news.py` 顶部的 `TOP_MEDIA` 列表即可。每条为 `(key, 中文名, 英文名, 域名)` 四元组；域名用于 `domain:` 后缀匹配。
