# Play Store Pulse: MoveInSync

A small, re-runnable tool that answers **"How are our Play Store ratings?"**, plus the one-time analysis and recommendation built with it.

- **Recommendation (start here):** [deliverables/MoveInSync_PlayStore_Recommendation.pdf](deliverables/MoveInSync_PlayStore_Recommendation.pdf)
- **Dashboard:** [output/report.html](output/report.html) (PDF copy in `deliverables/`)
- **Weekly digest:** [output/digest.md](output/digest.md)

## Run it

```bash
pip install -r requirements.txt
python run.py              # fetch new reviews, re-tag, rebuild report + digest
python run.py --no-scrape  # rebuild from data already in data/reviews.db
```

The first run pulls every review (about 10 minutes). After that, runs are incremental and only fetch reviews newer than what's stored. Each run also saves a snapshot of the store rating, so the headline trend builds up over time. `.github/workflows/weekly-pulse.yml` runs it every Monday and can post the digest to Slack.

## How it works

| Step | File | What it does |
|---|---|---|
| Config | `pulse/config.py` | Apps to track (own + competitors). Add a line to track another app. |
| Collect | `pulse/scrape.py` | `google-play-scraper` → SQLite (`reviews`, `snapshots`). Incremental, with retries. |
| Tag | `pulse/taxonomy.py` | 17 issue themes, built by hand-reading ~600 negative reviews. Each theme has an owner: `app` (mobile eng), `product`, or `service` (ops/vendors). Multi-label. |
| Analyse | `pulse/analyze.py` | Theme ranking by *share of stars lost* (5 − rating, split across a review's themes), change vs prior period, monthly trend, per-release table, reply-rate history, benchmark. |
| Report | `pulse/report.py` | Self-contained HTML dashboard, Markdown digest, JSON, and a tagged CSV for spreadsheet users. |

## How I got there (method note)

1. Found every MoveInSync app on Google Play, plus the closest competitors (Safetrax, Routematic).
2. Pulled all public reviews (27,665; 24,315 for the employee app) and the store metadata.
3. Read ~600 recent 1–2★ reviews by hand to find the recurring complaints, then encoded them as a rule-based taxonomy and tuned it by spot-checking samples per theme (≈80% precision; directional, not exact).
4. Analysed with pandas: trends, releases, stars-lost attribution, reply rates. Traced specific regressions to the release where they first appeared (e.g. the Play Store lockout → v12.16).
5. Wrote the prioritized recommendation, with each item tied to a metric this tool tracks.

**Tools:** Python, pandas, SQLite, google-play-scraper, Chart.js, Microsoft Edge (headless, for PDF export). Claude Code (AI coding assistant) helped write the code and speed up review triage. Findings were checked against the raw reviews.

## Limits

Public India/English storefront only, Android only. Google doesn't expose the store rating per period, so trends use written reviews. Keyword tagging is transparent and free, but it misses some reviews. The natural next step is an LLM classifier behind the same `classify()` interface.
