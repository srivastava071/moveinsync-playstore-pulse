"""Render the analysis as a self-contained HTML dashboard + a short Markdown digest."""

import html
import json
from datetime import date

from .config import OUTPUT_DIR

OWNER_LABEL = {"app": "Mobile eng", "product": "Product / UX", "service": "Ops / vendors", "unclassified": "Unspecific"}


def _pct(x, digits=0):
    return "–" if x is None else f"{x * 100:.{digits}f}%"


def _num(x, digits=2):
    return "–" if x is None else f"{x:.{digits}f}"


def _delta(cur, prev, pct=False, good_when_up=True):
    if cur is None or prev is None:
        return ""
    d = cur - prev
    if abs(d) < (0.005 if pct else 0.01):
        return '<span class="delta flat">flat vs prior period</span>'
    good = (d > 0) == good_when_up
    txt = f"{d * 100:+.1f} pts" if pct else f"{d:+.2f}"
    return f'<span class="delta {"good" if good else "bad"}">{txt} vs prior period</span>'


def digest_markdown(r):
    rec, rep = r["recent"], r["replies"]
    primary = next(a for a in r["apps"] if a["id"] == r["primary_app"])
    top = rec["themes"][:5]
    rising = sorted(rec["themes"], key=lambda t: -t["change_pts"])[:3]
    latest_ver = r["versions"][-1] if r["versions"] else None
    lines = [
        f"# Play Store pulse: {primary['name']} ({r['generated_for']})",
        "",
        f"- **Store rating:** {_num(primary.get('score'))} from {primary.get('ratings', 0):,} ratings",
        f"- **Last {rec['window_days']} days, written reviews:** {rec['reviews']} reviews, avg {_num(rec['avg'])} "
        f"(prior period {_num(rec['prev_avg'])}), {_pct(rec['neg_share'])} are 1-2★ (prior {_pct(rec['prev_neg_share'])})",
        f"- **Replies to 1-2★ reviews (last 90 days):** {_pct(rep['recent_negative_reply_rate'], 1)}",
    ]
    if latest_ver:
        lines.append(f"- **Latest release {latest_ver['minor']}:** avg {_num(latest_ver['avg'])}, "
                     f"{_pct(latest_ver['neg_share'])} negative ({latest_ver['reviews']} reviews)")
    lines += ["", "## Biggest drags on the rating (share of stars lost)"]
    for t in top:
        lines.append(f"1. **{t['label']}** ({OWNER_LABEL[t['owner']]}): {_pct(t['stars_lost_share'])} of stars lost, "
                     f"{t['neg_reviews']} negative reviews")
    lines += ["", "## Rising vs prior period"]
    for t in rising:
        if t["change_pts"] > 0:
            lines.append(f"- {t['label']}: {t['change_pts'] * 100:+.1f} pts share of negative reviews")
    lines += ["", "_Full dashboard: output/report.html_"]
    return "\n".join(lines)


def _quote_html(q):
    return (f'<blockquote><p>{html.escape(q["text"])}</p>'
            f'<cite>{"★" * q["score"]}{"☆" * (5 - q["score"])} · {q["date"]} · v{html.escape(str(q["version"] or "?"))}'
            f'{" · 👍 " + str(q["thumbs"]) if q["thumbs"] else ""}</cite></blockquote>')


def render_html(r):
    rec, rep = r["recent"], r["replies"]
    primary = next(a for a in r["apps"] if a["id"] == r["primary_app"])
    hist = primary.get("histogram") or [0] * 5
    hist_total = sum(hist) or 1
    owners = rec["stars_lost_by_owner"]

    theme_rows = []
    for i, t in enumerate(rec["themes"], 1):
        if t["neg_reviews"] == 0:
            continue
        chg = t["change_pts"] * 100
        chg_cls = "bad" if chg > 2 else "good" if chg < -2 else "flat"
        quotes = "".join(_quote_html(q) for q in t["quotes"]) or "<p class='muted'>No long-form quotes in window.</p>"
        theme_rows.append(f"""
        <details class="theme">
          <summary>
            <span class="rank">{i}</span>
            <span class="tlabel">{html.escape(t['label'])}</span>
            <span class="owner o-{t['owner']}">{OWNER_LABEL[t['owner']]}</span>
            <span class="bar"><span style="width:{min(t['stars_lost_share'] * 400, 100):.0f}%"></span></span>
            <span class="num">{_pct(t['stars_lost_share'])}</span>
            <span class="num">{t['neg_reviews']}</span>
            <span class="num {chg_cls}">{chg:+.0f} pts</span>
          </summary>
          <div class="quotes">{quotes}</div>
        </details>""")

    app_rows = []
    for a in r["apps"]:
        app_rows.append(f"""<tr class="{'own' if a['role'] == 'own' else ''}">
          <td>{html.escape(a['name'])}{' <span class="tag">competitor</span>' if a['role'] != 'own' else ''}</td>
          <td class="num">{_num(a.get('score'))}</td><td class="num">{a.get('ratings', 0):,}</td>
          <td class="num">{a['written_12m']:,}</td><td class="num">{_num(a['written_avg_12m'])}</td>
          <td class="num">{_pct(a['written_neg_12m'])}</td><td class="num">{_pct(a['reply_rate_12m'])}</td></tr>""")

    version_rows = "".join(
        f"<tr><td>{v['minor']}</td><td>{v['first_seen']}</td><td class='num'>{v['reviews']}</td>"
        f"<td class='num'>{_num(v['avg'])}</td><td class='num {'bad' if v['neg_share'] > 0.28 else ''}'>{_pct(v['neg_share'])}</td>"
        f"<td>{html.escape(', '.join(v['rising_themes'])) or '<span class=muted>–</span>'}</td></tr>"
        for v in reversed(r["versions"]))

    pc = r["prompt_complaints"]
    data_json = json.dumps({"monthly": r["monthly"], "versions": r["versions"]})

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Play Store Pulse</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --ink:#1c1c1a; --muted:#6b6b66; --line:#e6e5e0; --accent:#1f6f5c;
  --bad:#c0392b; --good:#1f7a4d; --c1:#1f6f5c; --c2:#d97a2b; --c3:#5470c6;
  --o-app:#e3edfb; --o-app-ink:#1d4e89; --o-product:#f6ebdc; --o-product-ink:#8a4d0f; --o-service:#ece6f6; --o-service-ink:#55308d; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#141413; --card:#1e1e1c; --ink:#ecebe6; --muted:#a3a29b;
  --line:#33322e; --accent:#5fc3a6; --bad:#ef7b6e; --good:#6fcf97; --c1:#5fc3a6; --c2:#f0a35e; --c3:#8aa2f0;
  --o-app:#1f2c3d; --o-app-ink:#9cc3f5; --o-product:#3a2c1b; --o-product-ink:#f0c18a; --o-service:#2c2340; --o-service-ink:#c6aef0; }} }}
:root[data-theme="dark"] {{ --bg:#141413; --card:#1e1e1c; --ink:#ecebe6; --muted:#a3a29b; --line:#33322e; --accent:#5fc3a6; --bad:#ef7b6e; --good:#6fcf97; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 Inter,system-ui,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; letter-spacing:-.01em; }} h2 {{ font-size:18px; margin:40px 0 12px; }}
.muted {{ color:var(--muted); }} .sub {{ color:var(--muted); margin:0 0 24px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
.kpi .v {{ font-size:28px; font-weight:700; letter-spacing:-.02em; }} .kpi .l {{ color:var(--muted); font-size:13px; }}
.delta {{ display:block; font-size:12px; margin-top:4px; }} .good {{ color:var(--good); }} .bad {{ color:var(--bad); }} .flat {{ color:var(--muted); }}
.callouts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:12px; margin-top:12px; }}
.callout {{ border-left:3px solid var(--accent); }} .callout b {{ display:block; margin-bottom:4px; }}
.charts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; }}
.chart {{ position:relative; height:260px; }}
.owners {{ display:flex; height:28px; border-radius:6px; overflow:hidden; margin:8px 0; }}
.owners span {{ display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; }}
.legend {{ display:flex; flex-wrap:wrap; gap:16px; font-size:13px; color:var(--muted); }}
.theme {{ background:var(--card); border:1px solid var(--line); border-radius:10px; margin-bottom:6px; }}
.theme summary {{ list-style:none; cursor:pointer; display:grid; grid-template-columns:28px 1fr 110px 120px 52px 44px 64px; gap:10px; align-items:center; padding:10px 14px; }}
.theme summary::-webkit-details-marker {{ display:none; }}
.thead {{ display:grid; grid-template-columns:28px 1fr 110px 120px 52px 44px 64px; gap:10px; padding:0 14px 6px; font-size:12px; color:var(--muted); }}
.rank {{ color:var(--muted); font-weight:600; }} .tlabel {{ font-weight:500; }}
.owner {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:99px; text-align:center; }}
.o-app {{ background:var(--o-app); color:var(--o-app-ink); }} .o-product {{ background:var(--o-product); color:var(--o-product-ink); }} .o-service {{ background:var(--o-service); color:var(--o-service-ink); }}
.bar {{ height:8px; background:var(--line); border-radius:4px; overflow:hidden; }} .bar span {{ display:block; height:100%; background:var(--accent); }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.quotes {{ padding:0 14px 12px 52px; }}
blockquote {{ margin:8px 0; padding:8px 12px; border-left:2px solid var(--line); }} blockquote p {{ margin:0; }}
cite {{ font-size:12px; color:var(--muted); font-style:normal; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }} th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ font-size:12px; color:var(--muted); font-weight:500; }} tr.own td:first-child {{ font-weight:600; }}
.tag {{ font-size:11px; color:var(--muted); border:1px solid var(--line); border-radius:99px; padding:1px 6px; margin-left:4px; }}
.scroll {{ overflow-x:auto; }}
.howto {{ margin-bottom:12px; font-size:14px; }} .howto ul {{ margin:6px 0 0; padding-left:18px; }}
.explain {{ color:var(--muted); margin:-4px 0 12px; font-size:14px; }}
footer {{ margin-top:48px; font-size:13px; color:var(--muted); }}
@media (max-width:720px) {{ .theme summary, .thead {{ grid-template-columns:22px 1fr 54px 60px; }}
  .theme summary .owner, .theme summary .bar, .theme summary .num:nth-last-child(2), .thead .hide-m {{ display:none; }} .quotes {{ padding-left:14px; }} }}
@media print {{ details.theme {{ break-inside:avoid; }} details.theme > .quotes {{ display:block; }} }}
</style></head>
<body><main>
<h1>Play Store Pulse: {html.escape(primary['name'])}</h1>
<p class="sub">Data through {r['generated_for']} · {rec['reviews']} written reviews in the last {rec['window_days']} days · regenerated by <code>python run.py</code></p>

<div class="card howto"><b>How to read this page</b>
<ul>
<li>This page is built from <b>real Play Store reviews</b> of the MoveInSync employee app. It updates every time the tool runs.</li>
<li><b>Written review</b> = a star rating that comes with text. <b>Bad review</b> = 1 or 2 stars.</li>
<li><b>"Last 90d"</b> = the last 3 months. <b>"vs prior period"</b> = compared with the 3 months before that.</li>
<li><b>Stars lost</b> = how far a review is from 5★. A 1★ review loses 4 stars, a 4★ review loses 1. Adding these up per problem shows which problems hurt the rating most.</li>
<li><b>pts</b> = percentage points. Going from 24% to 35% is +11 pts.</li>
</ul></div>

<div class="kpis">
  <div class="card kpi"><div class="l">Rating shown on the Play Store</div><div class="v">{_num(primary.get('score'))}★</div>
    <span class="delta flat">{primary.get('ratings', 0):,} ratings · {_pct(hist[0] / hist_total)} are 1★</span></div>
  <div class="card kpi"><div class="l">Average stars in written reviews (last 3 months)</div><div class="v">{_num(rec['avg'])}★</div>
    {_delta(rec['avg'], rec['prev_avg'])}</div>
  <div class="card kpi"><div class="l">Share of written reviews that are bad (1-2★)</div><div class="v">{_pct(rec['neg_share'])}</div>
    {_delta(rec['neg_share'], rec['prev_neg_share'], pct=True, good_when_up=False)}</div>
  <div class="card kpi"><div class="l">Bad reviews that got a reply from MoveInSync</div><div class="v">{_pct(rep['recent_negative_reply_rate'], 1)}</div>
    <span class="delta bad">was ~97% through Q1 2024</span></div>
</div>

<div class="callouts">
  <div class="card callout"><b>The headline hides the complaints</b>{_pct(hist[4] / hist_total)} of all store ratings are 5★ (mostly tap-only, prompted ratings), but people who write a review give {_num(rec['avg'])}★ on average and {_pct(rec['neg_share'])} of them give 1-2★. The written reviews are the ones new users read.</div>
  <div class="card callout"><b>Releases keep knocking the rating down</b>Recent releases with a spike in negative reviews: {', '.join(v['minor'] for v in r['versions'] if v['neg_share'] > 0.28) or 'none'}. Latest ({r['versions'][-1]['minor'] if r['versions'] else '?'}) is at {_pct(r['versions'][-1]['neg_share']) if r['versions'] else '–'} negative.</div>
  <div class="card callout"><b>The in-app rating prompt backfires</b>{pc['count']} reviews in the last 18 months complain that the trip rating can't be skipped (avg {_num(pc['avg_score'], 1)}★). Users then come to the Play Store to leave 1★.</div>
</div>

<h2>Who can fix the problems?</h2>
<p class="explain">Every complaint is labelled with the team that can fix it. The bar shows how much of the total damage (stars lost) belongs to each team.</p>
<div class="card">
  <div class="muted" style="font-size:13px">Share of stars lost in written reviews (5 − rating, split across the issues each review mentions), last {rec['window_days']} days</div>
  <div class="owners">
    <span style="width:{owners.get('app', 0) * 100:.1f}%;background:var(--o-app);color:var(--o-app-ink)">Mobile eng {_pct(owners.get('app'))}</span>
    <span style="width:{owners.get('product', 0) * 100:.1f}%;background:var(--o-product);color:var(--o-product-ink)">Product {_pct(owners.get('product'))}</span>
    <span style="width:{owners.get('service', 0) * 100:.1f}%;background:var(--o-service);color:var(--o-service-ink)">Ops {_pct(owners.get('service'))}</span>
    <span style="width:{owners.get('unclassified', 0) * 100:.1f}%;background:var(--line);color:var(--muted)">Unspecific {_pct(owners.get('unclassified'))}</span>
  </div>
  <div class="legend"><span><b>{_pct(owners.get('app', 0) + owners.get('product', 0))}</b> can be fixed by the team that builds the app (app developers + product). Ops problems (late cabs, routes, drivers) must go to the transport and vendor teams.</span></div>
</div>

<h2>Which problems hurt the rating most</h2>
<p class="explain">Problems are ranked by the share of stars lost in the last 3 months, biggest first. <b>Click any row</b> to read real reviews about that problem.</p>
<div class="thead"><span>#</span><span>Issue</span><span class="hide-m">Owner</span><span class="hide-m">Share of damage</span><span class="num">%</span><span class="num hide-m">Bad reviews</span><span class="num">Change</span></div>
{''.join(theme_rows)}
<p class="muted" style="font-size:13px">{_pct(rec['unclassified_share'])} of 1-2★ reviews name no specific issue ("worst app"). "Change" = how much more (red) or less (green) often this problem appears in bad reviews, compared with the 3 months before.</p>

<h2>How things changed over time</h2>
<p class="explain">Left: the green line is the average stars in written reviews each month (higher is better); the orange line is the share of bad reviews (lower is better). Right: the share of reviews MoveInSync replied to each month. Replies almost stopped in mid-2024.</p>
<div class="charts">
  <div class="card"><b>Average stars (green) and share of bad reviews (orange), by month</b><div class="chart"><canvas id="trend"></canvas></div></div>
  <div class="card"><b>Share of reviews MoveInSync replied to, by month</b><div class="chart"><canvas id="replies"></canvas></div></div>
</div>

<h2>How each app update performed</h2>
<p class="explain">Each row is an app update, newest first. A share of bad reviews in <span class="bad">red</span> means the update made things worse (good updates sit around 21-24%). The last column shows which complaints grew with that update.</p>
<div class="card scroll"><table><thead><tr><th>Version</th><th>Released (approx.)</th><th class="num">Reviews</th><th class="num">Avg stars</th><th class="num">Bad reviews</th><th>Complaints that grew vs the previous version</th></tr></thead>
<tbody>{version_rows}</tbody></table></div>

<h2>Comparison with other apps (last 12 months)</h2>
<p class="explain">MoveInSync's own apps compared with two competitors. "Store rating" is the number shown on the Play Store; the other columns use only written reviews.</p>
<div class="card scroll"><table><thead><tr><th>App</th><th class="num">Store rating</th><th class="num">Total ratings</th><th class="num">Written reviews</th><th class="num">Avg stars (written)</th><th class="num">Bad reviews</th><th class="num">Replied to</th></tr></thead>
<tbody>{''.join(app_rows)}</tbody></table></div>

<footer>
<p><b>Method.</b> Public Google Play reviews (India store, English) pulled with <code>google-play-scraper</code> into SQLite, tagged against a 17-issue taxonomy built by hand-reading ~600 negative reviews (<code>pulse/taxonomy.py</code>). Keyword tagging is directional, not exact: a review can carry several issues, and spot checks put precision at roughly 80%. The Play Store's own rating cannot be broken down by period publicly, so trends use written reviews.</p>
<p>Generated {date.today().isoformat()}.</p>
</footer>
</main>
<script>
const D = {data_json};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
Chart.defaults.color = css('--muted'); Chart.defaults.borderColor = css('--line');
const months = D.monthly.map(m => m.month);
new Chart(document.getElementById('trend'), {{ type:'line', data:{{ labels:months, datasets:[
  {{ label:'Avg rating', data:D.monthly.map(m => m.avg), borderColor:css('--c1'), backgroundColor:css('--c1'), yAxisID:'y', tension:.3, pointRadius:2 }},
  {{ label:'1-2★ share', data:D.monthly.map(m => m.neg_share * 100), borderColor:css('--c2'), backgroundColor:css('--c2'), yAxisID:'y1', tension:.3, pointRadius:2 }} ]}},
  options:{{ maintainAspectRatio:false, interaction:{{ mode:'index', intersect:false }}, plugins:{{ legend:{{ position:'bottom' }} }},
    scales:{{ y:{{ min:3, max:5, title:{{ display:true, text:'Avg ★' }} }}, y1:{{ position:'right', min:0, max:50, grid:{{ drawOnChartArea:false }}, ticks:{{ callback:v => v + '%' }} }} }} }} }});
new Chart(document.getElementById('replies'), {{ type:'bar', data:{{ labels:months, datasets:[
  {{ label:'Reviews answered', data:D.monthly.map(m => m.reply_rate * 100), backgroundColor:css('--c3') }} ]}},
  options:{{ maintainAspectRatio:false, plugins:{{ legend:{{ display:false }} }}, scales:{{ y:{{ min:0, max:100, ticks:{{ callback:v => v + '%' }} }} }} }} }});
</script>
</body></html>"""


def write(r):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "report.html").write_text(render_html(r), encoding="utf-8")
    (OUTPUT_DIR / "digest.md").write_text(digest_markdown(r), encoding="utf-8")
    (OUTPUT_DIR / "analysis.json").write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
    return OUTPUT_DIR / "report.html"
