"""Pull Play Store reviews + app metadata into a local SQLite DB.

Incremental: on re-runs it stops paging once it reaches reviews it already has,
so a weekly run only fetches what's new.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone

from google_play_scraper import Sort, app as gp_app, reviews as gp_reviews

from .config import APPS, COUNTRY, DB_PATH, LANG

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    user_name TEXT,
    content TEXT,
    score INTEGER,
    thumbs_up INTEGER,
    app_version TEXT,
    at TEXT,
    reply_content TEXT,
    replied_at TEXT,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_app_at ON reviews(app_id, at);
CREATE TABLE IF NOT EXISTS snapshots (
    app_id TEXT,
    taken_at TEXT,
    score REAL,
    ratings INTEGER,
    reviews INTEGER,
    histogram TEXT,
    installs INTEGER,
    version TEXT,
    updated TEXT,
    PRIMARY KEY (app_id, taken_at)
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def _iso(dt):
    return dt.isoformat() if dt else None


def snapshot_app(conn, app_id):
    """Store today's headline numbers so the rating trend can be tracked over time."""
    a = gp_app(app_id, lang=LANG, country=COUNTRY)
    conn.execute(
        "INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?)",
        (
            app_id,
            datetime.now(timezone.utc).date().isoformat(),
            a.get("score"),
            a.get("ratings"),
            a.get("reviews"),
            json.dumps(a.get("histogram")),
            a.get("realInstalls"),
            a.get("version"),
            a.get("lastUpdatedOn"),
        ),
    )
    conn.commit()
    return a


def fetch_reviews(conn, app_id, max_reviews=50000, batch=200):
    known = {r[0] for r in conn.execute("SELECT review_id FROM reviews WHERE app_id=?", (app_id,))}
    token, added, seen_known = None, 0, 0
    now = datetime.now(timezone.utc).isoformat()
    while added + seen_known < max_reviews:
        for attempt in range(3):
            try:
                result, token = gp_reviews(
                    app_id, lang=LANG, country=COUNTRY, sort=Sort.NEWEST,
                    count=batch, continuation_token=token,
                )
                break
            except Exception as e:  # network hiccups / throttling
                print(f"  retry {attempt + 1} for {app_id}: {e}")
                time.sleep(3 * (attempt + 1))
        else:
            break
        if not result:
            break
        new_rows = []
        for r in result:
            if r["reviewId"] in known:
                seen_known += 1
                continue
            new_rows.append((
                r["reviewId"], app_id, r.get("userName"), r.get("content"), r.get("score"),
                r.get("thumbsUpCount"), r.get("reviewCreatedVersion") or r.get("appVersion"),
                _iso(r.get("at")), r.get("replyContent"), _iso(r.get("repliedAt")), now,
            ))
        conn.executemany("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?,?)", new_rows)
        conn.commit()
        added += len(new_rows)
        # Sorted newest-first: a page with nothing new means we've caught up.
        if known and not new_rows:
            break
        if token is None or token.token is None:
            break
        time.sleep(0.5)
    return added


def run(apps=None):
    conn = connect()
    for a in apps or APPS:
        print(f"[scrape] {a['name']} ({a['id']})")
        try:
            meta = snapshot_app(conn, a["id"])
            print(f"  rating {meta.get('score')} from {meta.get('ratings')} ratings")
        except Exception as e:
            print(f"  snapshot failed: {e}")
        n = fetch_reviews(conn, a["id"])
        total = conn.execute("SELECT COUNT(*) FROM reviews WHERE app_id=?", (a["id"],)).fetchone()[0]
        print(f"  +{n} new reviews (total stored: {total})")
    conn.close()


if __name__ == "__main__":
    run()
