#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_html.py — 每日全球热点新闻简要 · 渲染层
读取 <date>.news.json（AI 后处理产出的最终结构化数据）渲染为单文件 HTML。
运行：python render_html.py <YYYY-MM-DD>
"""
import sys, os, json, argparse
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "..", "outputs", "news-digest")

# 类别配色（key: (中文名, 主色, 浅底)）
CAT_STYLE = {
    "economy":  ("经济", "#b8860b", "#fdf6e3"),
    "stock":    ("股票", "#c0392b", "#fdecea"),
    "tech":     ("科技", "#2980b9", "#eaf4fb"),
    "politics": ("政治", "#8e44ad", "#f5eef8"),
    "military": ("军事", "#566573", "#eceff1"),
}

DISCLAIMER = ("火爆度 = 0.6×GDELT 排名热度 + 0.4×AI 推理，含算法推理，非官方阅读量。"
              "新闻经 GDELT 聚合自 TOP20 全球官方媒体，链接均指向原始报道。")

# ---------- 访问计数器（纯前端，静态页可用） ----------
# 计数服务：abacus.jasoncameron.dev（免费、无需注册、CORS 开放），
# 键值按命名空间固定，故跨天重新生成页面时累计值连续不清零。
# 注：busuanzi（不蒜子）计数接口 2026-10 实测返回 502，已弃用。
COUNTER_BLOCK = """  <style>
    .visit-stat { display:flex; align-items:center; justify-content:center; gap:14px;
      flex-wrap:wrap; margin-top:18px; padding:12px 18px; background:#10182a;
      border:1px solid var(--line); border-radius:12px; color:var(--muted); font-size:13px; }
    .visit-stat .vl { display:flex; align-items:baseline; gap:4px; }
    .visit-stat b { color:#ffd479; font-size:17px; font-weight:700;
      font-variant-numeric:tabular-nums; letter-spacing:.4px; }
    .visit-stat .sep { color:#3a4a6b; }
    .visit-stat .live { width:7px; height:7px; border-radius:50%; background:#3ddc97;
      box-shadow:0 0 0 3px rgba(61,220,151,.15); }
    .visit-stat .hint { color:#5d6b85; font-size:12px; }
    @media (max-width:560px) { .visit-stat { gap:10px; font-size:12px; } .visit-stat b { font-size:15px; } }
  </style>
  <div class="visit-stat" id="visit-stat" aria-live="polite">
    <span class="live" aria-hidden="true"></span>
    <span class="vl">累计访问 <b id="vs-pv">···</b> 人次</span>
    <span class="sep">|</span>
    <span class="vl">访客 <b id="vs-uv">···</b> 人</span>
    <span class="hint" id="vs-hint"></span>
  </div>
  <script>
  (function () {
    var NS = "global-news-digest", BASE = "https://abacus.jasoncameron.dev";
    var elPv = document.getElementById("vs-pv"),
        elUv = document.getElementById("vs-uv"),
        elHint = document.getElementById("vs-hint");
    var UV_FLAG = "gnd_uv_seen_v1";

    function call(path) {
      var ctrl = ("AbortController" in window) ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 6000) : null;
      return fetch(BASE + path, { mode: "cors", cache: "no-store",
        signal: ctrl ? ctrl.signal : undefined })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(function (j) { if (timer) clearTimeout(timer); return j; });
    }

    // 累计访问人次：每次打开 +1
    var pv = call("/hit/" + NS + "/total");

    // 访客数（近似）：同一浏览器只计一次
    var firstVisit = false;
    try { firstVisit = !localStorage.getItem(UV_FLAG); } catch (e) { firstVisit = false; }
    var uv = firstVisit ? call("/hit/" + NS + "/visitors")
      : call("/get/" + NS + "/visitors").catch(function () { return call("/hit/" + NS + "/visitors"); });
    if (firstVisit) { try { localStorage.setItem(UV_FLAG, "1"); } catch (e) {} }

    pv.then(function (j) { elPv.textContent = (j && j.value != null) ? j.value : "—"; })
      .catch(function () {
        elPv.textContent = "—";
        elHint.textContent = "（统计服务暂不可用）";
      });

    uv.then(function (j) { elUv.textContent = (j && j.value != null) ? j.value : "—"; })
      .catch(function () { elUv.textContent = "—"; });
  })();
  </script>
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_category(cat, style):
    key = cat.get("key", "")
    name = cat.get("name", style[0])
    items = cat.get("items", []) or []
    color, light = style[1], style[2]
    if not items:
        body = (f'<div class="empty">本类暂无符合条件的新闻（可能该日 GDELT 无相关报道）。</div>')
    else:
        rows = []
        for it in items:
            rank = it.get("rank", "")
            title = esc(it.get("title", ""))
            summary = esc(it.get("summary", ""))
            source = esc(it.get("source", ""))
            hot = int(it.get("hotness", 0) or 0)
            url = esc(it.get("url", ""))
            rows.append(f"""
            <tr>
              <td class="rank">{rank}</td>
              <td class="title"><a href="{url}" target="_blank" rel="noopener">{title}</a></td>
              <td class="summary">{summary}</td>
              <td class="source">{source}</td>
              <td class="hot">
                <div class="hot-bar"><span style="width:{hot}%"></span></div>
                <div class="hot-num">{hot}</div>
              </td>
              <td class="link"><a href="{url}" target="_blank" rel="noopener">原文 ↗</a></td>
            </tr>""")
        body = f"""
        <div class="table-wrap">
        <table>
          <thead><tr>
            <th class="c-rank">序号</th><th class="c-title">新闻名称</th>
            <th class="c-sum">新闻简要</th><th class="c-src">来源机构</th>
            <th class="c-hot">火爆度</th><th class="c-link">来源链接</th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        </div>"""
    return f"""
    <section class="cat">
      <div class="cat-head" style="background:{color}"><span class="dot"></span>{esc(name)} · TOP {len(items) if items else 0}</div>
      {body}
    </section>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="目标日期 YYYY-MM-DD")
    args = ap.parse_args()
    date = args.date
    json_path = os.path.join(OUT_DIR, f"{date}.news.json")
    if not os.path.exists(json_path):
        sys.stderr.write(f"找不到 {json_path}\n请先运行 fetch_news.py 并完成 AI 后处理（生成 .news.json）。\n")
        sys.exit(1)
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    cats = data.get("categories", [])
    gen = data.get("generated_at", "")
    try:
        gen_disp = datetime.fromisoformat(gen.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        gen_disp = gen

    sections = []
    order = ["economy", "stock", "tech", "politics", "military"]
    # 按固定顺序 + 其余补齐
    seen = set()
    for k in order:
        for c in cats:
            if c.get("key") == k:
                sections.append(render_category(c, CAT_STYLE.get(k, (c.get("name", ""), "#34495e", "#eee"))))
                seen.add(id(c))
                break
    for c in cats:
        if id(c) not in seen:
            sections.append(render_category(c, CAT_STYLE.get(c.get("key"), (c.get("name", ""), "#34495e", "#eee"))))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日全球热点新闻简要 · {date}</title>
<style>
  :root {{ --bg:#0f1420; --card:#161d2e; --ink:#e8edf6; --muted:#9fb0c8; --line:#26324a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:linear-gradient(180deg,#0c111c,#0f1420 40%); color:var(--ink);
         font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",Roboto,Helvetica,Arial,sans-serif;
         line-height:1.6; padding:28px 16px 60px; }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  header.top {{ text-align:center; margin-bottom:8px; }}
  header.top h1 {{ font-size:28px; margin:0 0 6px; letter-spacing:.5px; }}
  header.top .sub {{ color:var(--muted); font-size:14px; }}
  .badge {{ display:inline-block; margin-top:10px; padding:6px 12px; border-radius:999px;
           background:#1d2740; color:#ffd479; font-size:12px; border:1px solid #3a4a6b; }}
  .cat {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
         margin:18px 0; overflow:hidden; box-shadow:0 6px 20px rgba(0,0,0,.25); }}
  .cat-head {{ color:#fff; font-size:17px; font-weight:700; padding:12px 18px; display:flex; align-items:center; gap:10px; }}
  .cat-head .dot {{ width:10px; height:10px; border-radius:50%; background:rgba(255,255,255,.85); }}
  .table-wrap {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; min-width:760px; }}
  thead th {{ background:#10182a; color:var(--muted); font-weight:600; text-align:left;
             padding:11px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }}
  tbody td {{ padding:12px; border-bottom:1px solid var(--line); vertical-align:top; }}
  tbody tr:hover {{ background:#1b2438; }}
  .rank {{ font-weight:700; color:#ffd479; width:46px; text-align:center; }}
  .title a {{ color:#7fb4ff; text-decoration:none; font-weight:600; }}
  .title a:hover {{ text-decoration:underline; }}
  .summary {{ color:#cfd9ea; max-width:340px; }}
  .source {{ color:var(--muted); white-space:nowrap; }}
  .hot {{ width:150px; }}
  .hot-bar {{ height:8px; background:#22304a; border-radius:6px; overflow:hidden; }}
  .hot-bar span {{ display:block; height:100%; background:linear-gradient(90deg,#ff9a3c,#ff4d4f); }}
  .hot-num {{ font-size:12px; color:#ffb86b; margin-top:3px; }}
  .link a {{ color:#7fb4ff; text-decoration:none; white-space:nowrap; }}
  .empty {{ padding:22px; color:var(--muted); text-align:center; }}
  .disclaimer {{ margin-top:26px; padding:14px 18px; background:#10182a; border:1px solid var(--line);
                border-radius:12px; color:var(--muted); font-size:12.5px; }}
  footer.ft {{ text-align:center; color:#5d6b85; font-size:12px; margin-top:24px; }}
  @media (max-width:560px) {{
    body {{ padding:16px 8px 40px; }}
    header.top h1 {{ font-size:22px; }}
    table {{ font-size:13px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>🌐 每日全球热点新闻简要</h1>
    <div class="sub">数据日期（北京时间）：<b>{date}</b> ｜ 生成时间：{gen_disp}</div>
    <div class="badge">⚠ 火爆度含 AI 推理，非官方阅读量</div>
  </header>
  {''.join(sections)}
  <div class="disclaimer"><b>说明：</b>{DISCLAIMER}<br>数据来源：GDELT Doc 2.0（聚合自 TOP20 全球官方媒体）。本页为自动化聚合，仅供参考，不构成投资或决策建议。</div>
  {COUNTER_BLOCK}
  <footer class="ft">由 WorkBuddy 技能「全球热点新闻简要」生成 · global-news-digest</footer>
</div>
</body>
</html>"""

    out_html = os.path.join(OUT_DIR, f"{date}.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    sys.stderr.write(f"已生成 HTML：{out_html}\n")
    print(out_html)


if __name__ == "__main__":
    main()
