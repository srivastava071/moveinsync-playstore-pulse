"""Turn the raw review DB into the numbers the report needs.

Everything here is deterministic and re-runnable: same DB in, same report out.
"""

import json
import re
import sqlite3
from datetime import timedelta

import pandas as pd

from .config import APPS, DB_PATH, PRIMARY_APP
from .taxonomy import THEME_BY_ID, THEMES, classify

WINDOW_DAYS = 90  # "recent" window used for the headline theme ranking


def load():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM reviews", conn, parse_dates=["at", "replied_at"])
    snaps = pd.read_sql("SELECT * FROM snapshots", conn)
    conn.close()
    df["content"] = df["content"].fillna("")
    df["themes"] = df["content"].map(classify)
    df["minor"] = df["app_version"].fillna("").str.extract(r"^(\d+\.\d+)")[0]
    return df, snaps


def _stars_lost(sub):
    """Attribute each review's lost stars (5 - score) equally across its themes."""
    lost = {}
    for score, themes in zip(sub["score"], sub["themes"]):
        if not themes:
            themes = ["unclassified"]
        share = (5 - score) / len(themes)
        for t in themes:
            lost[t] = lost.get(t, 0) + share
    return lost


def _pick_quotes(sub, k=3):
    """Representative quotes: most-upvoted first, then most recent; skip one-liners."""
    s = sub[sub["content"].str.len().between(60, 400)]
    s = s.sort_values(["thumbs_up", "at"], ascending=[False, False])
    return [
        {"text": r.content.strip().replace("\n", " "), "score": int(r.score),
         "date": r.at.date().isoformat(), "version": r.app_version, "thumbs": int(r.thumbs_up or 0)}
        for r in s.head(k).itertuples()
    ]


def theme_table(df, end, days=WINDOW_DAYS):
    cur = df[(df["at"] > end - timedelta(days=days)) & (df["at"] <= end)]
    prev = df[(df["at"] > end - timedelta(days=2 * days)) & (df["at"] <= end - timedelta(days=days))]
    cur_neg, prev_neg = cur[cur.score <= 2], prev[prev.score <= 2]
    lost_cur = _stars_lost(cur)
    total_lost = sum(lost_cur.values()) or 1
    rows = []
    for t in THEMES:
        tid = t["id"]
        in_cur = cur_neg[cur_neg["themes"].map(lambda x: tid in x)]
        in_prev = prev_neg[prev_neg["themes"].map(lambda x: tid in x)]
        share = len(in_cur) / max(len(cur_neg), 1)
        prev_share = len(in_prev) / max(len(prev_neg), 1)
        rows.append({
            "id": tid, "label": t["label"], "owner": t["owner"],
            "neg_reviews": len(in_cur), "share_of_negative": share, "prev_share": prev_share,
            "change_pts": share - prev_share,
            "stars_lost_share": lost_cur.get(tid, 0) / total_lost,
            # If this theme vanished, how much would the written-review average rise?
            "avg_lift_if_fixed": lost_cur.get(tid, 0) / max(len(cur), 1),
            "quotes": _pick_quotes(in_cur),
        })
    rows.sort(key=lambda r: -r["stars_lost_share"])
    by_owner = {}
    for r in rows:
        by_owner[r["owner"]] = by_owner.get(r["owner"], 0) + r["stars_lost_share"]
    by_owner["unclassified"] = lost_cur.get("unclassified", 0) / total_lost
    unclassified = cur_neg[cur_neg["themes"].map(len) == 0]
    return {
        "window_days": days, "reviews": len(cur), "negative": len(cur_neg),
        "avg": float(cur.score.mean()) if len(cur) else None,
        "prev_avg": float(prev.score.mean()) if len(prev) else None,
        "neg_share": len(cur_neg) / max(len(cur), 1),
        "prev_neg_share": len(prev_neg) / max(len(prev), 1),
        "unclassified_share": len(unclassified) / max(len(cur_neg), 1),
        "stars_lost_by_owner": by_owner,
        "themes": rows,
    }


def monthly(df, months=36):
    end = df["at"].max()
    d = df[df["at"] > end - pd.DateOffset(months=months)].copy()
    d["month"] = d["at"].dt.to_period("M").astype(str)
    g = d.groupby("month").agg(
        reviews=("score", "size"), avg=("score", "mean"),
        neg_share=("score", lambda s: (s <= 2).mean()),
        reply_rate=("reply_content", lambda s: s.notna().mean()),
    ).reset_index()
    return g.round(4).to_dict("records")


def versions(df, months=12, min_reviews=40):
    end = df["at"].max()
    d = df[(df["at"] > end - pd.DateOffset(months=months)) & df["minor"].notna()]
    g = d.groupby("minor").agg(
        reviews=("score", "size"), avg=("score", "mean"),
        neg_share=("score", lambda s: (s <= 2).mean()), first_seen=("at", "min"),
    ).reset_index()
    g = g[g.reviews >= min_reviews].sort_values("first_seen")
    g["first_seen"] = g["first_seen"].dt.date.astype(str)
    out = g.round(4).to_dict("records")
    # Which themes jumped in each release vs. the release before it?
    neg = d[d.score <= 2]
    prev = None
    for row in out:
        sub = neg[neg["minor"] == row["minor"]]
        counts = {t["id"]: sub["themes"].map(lambda x, i=t["id"]: i in x).mean() if len(sub) else 0 for t in THEMES}
        if prev:
            jumps = sorted(((counts[k] - prev[k], k) for k in counts), reverse=True)[:2]
            row["rising_themes"] = [THEME_BY_ID[k]["label"] for diff, k in jumps if diff > 0.05]
        else:
            row["rising_themes"] = []
        prev = counts
    return out


def reply_stats(df):
    d = df.copy()
    d["quarter"] = d["at"].dt.to_period("Q").astype(str)
    q = d.groupby("quarter").reply_content.apply(lambda s: s.notna().mean()).reset_index(name="reply_rate")
    replies = d[d.reply_content.notna()]
    last_reply = replies["at"].max()
    neg = d[d.score <= 2]
    recent_neg = neg[neg["at"] > d["at"].max() - timedelta(days=90)]
    return {
        "by_quarter": q.tail(16).round(4).to_dict("records"),
        "recent_negative_reply_rate": float(recent_neg.reply_content.notna().mean()) if len(recent_neg) else 0,
        "last_reply": last_reply.date().isoformat() if pd.notna(last_reply) else None,
    }


def prompt_complaints(df):
    pat = re.compile(
        r"(rat(e|ing)|feedback|review).{0,60}(every|force|skip|compuls|mandatory|pop|only 4|4 or 5|asking)"
        r"|(force|skip|compuls|mandatory).{0,40}(rat(e|ing)|feedback|review)", re.I)
    m = df[df["content"].map(lambda t: bool(pat.search(t)))]
    return {"count": len(m), "avg_score": float(m.score.mean()) if len(m) else None,
            "quotes": _pick_quotes(m.sort_values("at", ascending=False), k=4)}


def mismatched_stars(df, end):
    """5-star reviews whose text is clearly a complaint: a hint that some stars aren't deliberate."""
    d = df[(df["at"] > end - timedelta(days=180)) & (df.score >= 4)]
    bad = d[d["themes"].map(lambda t: bool(set(t) & {"login_otp", "crash_wont_open", "integrity_block", "session_logout"}))]
    return {"count": len(bad), "of": len(d)}


def headline(snaps, df):
    latest = snaps.sort_values("taken_at").groupby("app_id").tail(1)
    out = []
    for a in APPS:
        row = latest[latest.app_id == a["id"]]
        sub = df[(df.app_id == a["id"]) & (df["at"] > df["at"].max() - timedelta(days=365))]
        item = {"id": a["id"], "name": a["name"], "role": a["role"],
                "written_12m": len(sub),
                "written_avg_12m": float(sub.score.mean()) if len(sub) else None,
                "written_neg_12m": float((sub.score <= 2).mean()) if len(sub) else None,
                "reply_rate_12m": float(sub.reply_content.notna().mean()) if len(sub) else None}
        if len(row):
            r = row.iloc[0]
            hist = json.loads(r.histogram) if r.histogram else None
            item.update({"score": r.score, "ratings": int(r.ratings or 0), "histogram": hist,
                         "installs": int(r.installs or 0), "version": r.version, "snapshot_date": r.taken_at})
        out.append(item)
    return out


def run():
    df, snaps = load()
    primary = df[df.app_id == PRIMARY_APP]
    end = primary["at"].max()
    result = {
        "generated_for": end.date().isoformat(),
        "primary_app": PRIMARY_APP,
        "apps": headline(snaps, df),
        "recent": theme_table(primary, end),
        "half_year": theme_table(primary, end, days=180),
        "monthly": monthly(primary),
        "versions": versions(primary),
        "replies": reply_stats(primary),
        "prompt_complaints": prompt_complaints(primary[primary["at"] > end - timedelta(days=540)]),
        "mismatched_stars": mismatched_stars(primary, end),
        "owners": {t["id"]: t["owner"] for t in THEMES},
    }
    return result, df


if __name__ == "__main__":
    res, _ = run()
    print(json.dumps({k: v for k, v in res.items() if k in ("recent", "versions")}, indent=1, default=str)[:6000])
