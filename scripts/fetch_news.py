#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_news.py — 每日全球热点新闻简要 · 抓取层（v1.1 加速版）

加速策略（vs 旧版 20 次请求 / ~152s 纯等待）：
  - 每类用「关键词 + 域名分块」直接查询：20 个 TOP20 媒体域名按字符预算切成约 2 块，
    每块 1 次 GDELT 请求并带 domain: 过滤，5 类共约 10 次请求（旧版 20 次）。
  - 全局统一节流（DEFAULT_GAP 秒/次，>= GDELT 5s 限流），去掉类别/块间的重复 sleep。

准确性不变：仍仅保留 TOP20 媒体、时间窗过滤、URL/标题去重，输出结构与旧版完全一致，
兼容 render_html.py 与 AI 后处理。
仅依赖 requests。运行：python fetch_news.py [YYYY-MM-DD]
"""
import sys, os, json, time, argparse
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    sys.stderr.write("缺少 requests，请先安装：pip install requests\n")
    sys.exit(2)

# ---------- 常量：TOP20 媒体（均衡版） ----------
TOP_MEDIA = [
    ("reuters", "路透社", "Reuters", "reuters.com"),
    ("ap", "美联社", "Associated Press", "apnews.com"),
    ("bbc", "英国广播公司", "BBC", "bbc.com"),
    ("bloomberg", "彭博社", "Bloomberg", "bloomberg.com"),
    ("cnbc", "消费者新闻与商业频道", "CNBC", "cnbc.com"),
    ("ft", "金融时报", "Financial Times", "ft.com"),
    ("wsj", "华尔街日报", "The Wall Street Journal", "wsj.com"),
    ("nhk", "日本放送协会", "NHK", "nhk.or.jp"),
    ("dw", "德国之声", "Deutsche Welle", "dw.com"),
    ("aljazeera", "半岛电视台", "Al Jazeera", "aljazeera.com"),
    ("xinhua", "新华社", "Xinhua", "xinhuanet.com"),
    ("cgtn", "中国国际电视台", "CGTN", "cgtn.com"),
    ("nikkei", "日本经济新闻", "Nikkei", "nikkei.com"),
    ("lemonde", "世界报", "Le Monde", "lemonde.fr"),
    ("guardian", "卫报", "The Guardian", "theguardian.com"),
    ("nyt", "纽约时报", "The New York Times", "nytimes.com"),
    ("wapo", "华盛顿邮报", "The Washington Post", "washingtonpost.com"),
    ("cnn", "美国有线电视新闻网", "CNN", "cnn.com"),
    ("afp", "法新社", "Agence France-Presse", "afp.com"),
    ("scmp", "南华早报", "South China Morning Post", "scmp.com"),
]

# ---------- 常量：5 类关键词 ----------
CATEGORIES = {
    "economy": ("经济", [
        "economy", "inflation", "gdp", "recession", "tariff",
        "banking", "federal", "monetary",
    ]),
    "stock": ("股票", [
        "stock", "stocks", "equities", "nasdaq", "shares",
        "ipo", "market", "dow",
    ]),
    "tech": ("科技", [
        "technology", "semiconductor", "chip", "cybersecurity", "spacecraft",
        "software", "robotics", "internet", "quantum",
    ]),
    "politics": ("政治", [
        "politics", "election", "government", "diplomacy", "parliament",
        "summit", "policy", "sanction",
    ]),
    "military": ("军事", [
        "military", "war", "defense", "missile", "nato",
        "troops", "navy", "conflict",
    ]),
}

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
BJ = timezone(timedelta(hours=8))          # 北京时间 = UTC+8
UTC = timezone.utc
MAX_RECORDS = 250                           # 单次请求候选上限
CAP_PER_CAT = 40                            # 每类候选上限（供 AI 后处理精选）
DEFAULT_GAP = 7                             # GDELT 限流 1 次/5 秒，留 2 秒余量
QRY_CHAR_CAP = 260                          # query 总长上限约 300，留 40 余量
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "..", "outputs", "news-digest")


def domain_to_source(domain: str):
    """按域名后缀匹配机构中文名；非 TOP20 媒体返回 None。"""
    d = (domain or "").lower().strip()
    for _k, zh, _en, dom in TOP_MEDIA:
        if d == dom or d.endswith("." + dom):
            return zh
    return None


def all_domains():
    return [m[3] for m in TOP_MEDIA]


def beijing_yesterday() -> datetime:
    return datetime.now(BJ).date() - timedelta(days=1)


def date_window(target_date):
    """北京时间 target_date 00:00 ~ 24:00 → UTC 的 YYYYMMDDHHMMSS。"""
    start_bj = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=BJ)
    end_bj = start_bj + timedelta(hours=24) - timedelta(seconds=1)
    fmt = "%Y%m%d%H%M%S"
    return start_bj.astimezone(UTC).strftime(fmt), end_bj.astimezone(UTC).strftime(fmt)


def build_query_domains(keywords, domains):
    """关键词（整体括号）+ 域名分块（整体括号），满足 GDELT OR 语法与长度上限。"""
    return "(" + " OR ".join(keywords) + ") (" + " OR ".join("domain:" + d for d in domains) + ")"


def split_domains_by_chars(keyword_part, domains, cap=QRY_CHAR_CAP):
    """按字符预算把域名切成若干块，保证每块的完整 query 长度 < cap。"""
    base = len(keyword_part) + 2  # 外层括号
    chunks, cur, curlen = [], [], base
    for d in domains:
        part = len("domain:" + d) + 4  # " OR "
        if cur and curlen + part > cap:
            chunks.append(cur)
            cur, curlen = [], base
        cur.append(d)
        curlen += part
    if cur:
        chunks.append(cur)
    return chunks


def parse_seendate(s: str):
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except Exception:
        return None


def gdelt_query(query, start, end, sess, attempt=0):
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "sortby": "HybridRel",
        "maxrecords": MAX_RECORDS,
        "startdatetime": start,
        "enddatetime": end,
    }
    try:
        r = sess.get(GDELT_URL, params=params, timeout=60)
    except Exception as e:
        if attempt < 3:
            time.sleep(10 * (attempt + 1))
            return gdelt_query(query, start, end, sess, attempt + 1)
        return None, f"request error: {e}"
    if r.status_code == 429:
        if attempt < 3:
            # GDELT 限流窗口约 5 秒：温和退避 6/12/18 秒即可，避免过度等待雪崩
            time.sleep(6 * (attempt + 1))
            return gdelt_query(query, start, end, sess, attempt + 1)
        return None, "429 rate limited (gave up after retries)"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text[:160]}"
    body = r.text.strip()
    if not body.startswith("{"):
        return None, f"non-json body: {body[:160]}"
    try:
        return r.json().get("articles", []), None
    except Exception as e:
        return None, f"json parse fail: {e} | body={r.text[:160]}"


class Throttled:
    """全局串行节流器：除首次外，每次请求前 sleep gap 秒，保证 >= 限流间隔。"""
    def __init__(self, sess, gap):
        self.sess = sess
        self.gap = gap
        self.first = True

    def query(self, query, start, end):
        if not self.first:
            time.sleep(self.gap)
        self.first = False
        return gdelt_query(query, start, end, self.sess)


def dedupe_key(title):
    return (title or "").lower().replace(" ", "").replace("-", "")


def collect_from_articles(arts, s_utc, e_utc, seen_urls, seen_norm, cap):
    """从 GDELT 文章列表里过滤（TOP20/时间窗/去重）并收集候选。"""
    out = []
    for a in arts:
        url = (a.get("url") or "").strip()
        title = (a.get("title") or "").strip()
        domain = (a.get("domain") or "").strip()
        if not url or not title:
            continue
        if domain_to_source(domain) is None:     # 仅保留 TOP20 媒体
            continue
        sd = parse_seendate(a.get("seendate", ""))
        if sd is None:
            continue
        if not (s_utc - timedelta(hours=1) <= sd <= e_utc + timedelta(hours=1)):
            continue
        dk = dedupe_key(title)
        if url in seen_urls or dk in seen_norm:
            continue
        seen_urls.add(url)
        seen_norm.add(dk)
        out.append({
            "title": title,
            "url": url,
            "domain": domain,
            "source": domain_to_source(domain),
            "seendate": a.get("seendate", ""),
            "language": a.get("language", ""),
            "sourcecountry": a.get("sourcecountry", ""),
            "gdelt_rank": 0,
        })
        if len(out) >= cap:
            break
    return out


def fetch_category(keywords, start, end, th, s_utc, e_utc, cap=CAP_PER_CAT):
    """每类：关键词 + 域名分块（约 2 块）串行查询，合并去重后返回候选。"""
    kw_query = "(" + " OR ".join(keywords) + ")"
    chunks = split_domains_by_chars(kw_query, all_domains())
    seen_urls, seen_norm = set(), set()
    items, errs = [], []
    for chunk in chunks:
        dq = build_query_domains(keywords, chunk)
        arts, err = th.query(dq, start, end)
        if err:
            errs.append(err)
            continue
        items += collect_from_articles(arts, s_utc, e_utc, seen_urls, seen_norm, cap)
        if len(items) >= cap:
            break
    items = items[:cap]
    for i, it in enumerate(items):
        it["gdelt_rank"] = i + 1
    return items, ("; ".join(errs) if errs and not items else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", help="目标日期 YYYY-MM-DD（北京时间），默认昨天")
    ap.add_argument("--only", help="仅抓取指定类别 key（economy/stock/tech/politics/military）")
    ap.add_argument("--gap", type=int, default=DEFAULT_GAP, help="请求间隔秒数（>=5，默认 7）")
    ap.add_argument("--presleep", type=int, default=0, help="开始前等待秒数")
    ap.add_argument("--cooldown", type=int, default=30, help="启动前冷却秒数，避开限流窗口（默认 30）")
    args = ap.parse_args()
    if args.date:
        try:
            target = datetime.strptime(args.date, "%Y-%m-%d").date()
        except Exception:
            sys.stderr.write("日期格式应为 YYYY-MM-DD\n"); sys.exit(1)
    else:
        target = beijing_yesterday()

    gap = max(5, args.gap)
    if args.presleep:
        time.sleep(args.presleep)
    if args.cooldown:
        sys.stderr.write(f"  [冷却] 启动前等待 {args.cooldown}s 避开 GDELT 限流窗口…\n")
        time.sleep(args.cooldown)

    start, end = date_window(target)
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{target.isoformat()}.raw.news.json")

    sess = requests.Session()
    sess.headers.update({"User-Agent": "global-news-digest/1.1 (+local)"})
    th = Throttled(sess, gap)

    s_utc = datetime.strptime(start, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    e_utc = datetime.strptime(end, "%Y%m%d%H%M%S").replace(tzinfo=UTC)

    result = {
        "date": target.isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "window_utc": {"start": start, "end": end},
        "source": "GDELT Doc 2.0",
        "categories": {},
    }

    cats = {k: v for k, v in CATEGORIES.items() if not args.only or k == args.only}
    t0 = time.time()
    req_count = 0
    for key, (zh, keywords) in cats.items():
        items, err = fetch_category(keywords, start, end, th, s_utc, e_utc)
        req_count += len(split_domains_by_chars("(" + " OR ".join(keywords) + ")", all_domains()))
        if err:
            result["categories"][key] = {"name": zh, "error": err, "items": []}
            sys.stderr.write(f"  [!] {zh}: {err}\n")
        else:
            result["categories"][key] = {"name": zh, "error": None, "items": items}
            sys.stderr.write(f"  [ok] {zh}: {len(items)} 条候选\n")

    if args.only and os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                prev = json.load(f)
            prev["categories"][args.only] = result["categories"][args.only]
            result = prev
        except Exception:
            pass

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"\n已写出原始候选：{out_path}\n")
    sys.stderr.write(f"耗时：{time.time() - t0:.1f}s（{len(cats)} 类，约 {req_count} 次 GDELT 请求）\n")
    print(out_path)


if __name__ == "__main__":
    main()
