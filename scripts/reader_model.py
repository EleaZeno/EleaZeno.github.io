#!/usr/bin/env python3
"""Reader model: what the site covered, and what the reader cares about.

Why this exists
---------------
The daily job needs three things a stateless prompt cannot provide:

1. Coverage memory - what was already written, so it stops repeating itself
   and can build on earlier pieces instead.
2. A reader profile - which topics actually land, learned from explicit
   feedback rather than guessed.
3. Topic candidates - a durable queue, so an idea noticed on Tuesday is
   still there on Friday.

Storage is SQLite on the persistent volume. Everything is addressable by
stable ids so repeated runs are idempotent.

CLI (all output JSON, for consumption by the agent):

    reader_model.py init
    reader_model.py record-post <path.md>
    reader_model.py brief [--days 14]
    reader_model.py suggest [--limit 8]
    reader_model.py add-candidate "<topic>" [--domain ai] [--why "..."]
       [--source URL] [--score 0.5]
    reader_model.py claim-candidate <id>
    reader_model.py feedback "<topic-or-tag>" --signal like|dislike|more|less
       [--note "..."]
    reader_model.py profile
    reader_model.py covered "<query>"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Persistent volume: /root and ~/.hermes are overlayfs here and do not
# survive a pod rebuild, so state lives next to the repo instead.
DEFAULT_DB = Path(
    os.environ.get("BLOG_DB", "/home/shared/workspace/blog/.data/reader_model.db")
)
REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "src" / "content" / "posts"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    pub_date     TEXT NOT NULL,
    domain       TEXT NOT NULL,
    topic        TEXT,
    confidence   TEXT,
    description  TEXT,
    body_chars   INTEGER DEFAULT 0,
    source_count INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_tags (
    post_id TEXT NOT NULL,
    tag     TEXT NOT NULL,
    PRIMARY KEY (post_id, tag)
);

CREATE TABLE IF NOT EXISTS candidates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    topic      TEXT NOT NULL UNIQUE,
    domain     TEXT NOT NULL DEFAULT 'ai',
    why        TEXT,
    source_url TEXT,
    score      REAL NOT NULL DEFAULT 0.5,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject    TEXT NOT NULL,
    signal     TEXT NOT NULL,
    weight     REAL NOT NULL,
    note       TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(pub_date DESC);
CREATE INDEX IF NOT EXISTS idx_cand_status ON candidates(status, score DESC);
CREATE INDEX IF NOT EXISTS idx_fb_subject ON feedback(subject);
"""

# Explicit feedback weights. "more"/"less" are stronger than a bare
# like/dislike because they are instructions, not reactions.
SIGNAL_WEIGHTS = {"like": 1.0, "more": 2.0, "dislike": -1.0, "less": -2.0}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal YAML frontmatter reader.

    Handles exactly what the generator emits: scalars, inline ``[a, b]``
    lists, and nested ``- key: value`` blocks (used by ``sources``). Avoids a
    PyYAML dependency so the CLI runs anywhere python3 does.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")

    data: dict = {}
    current_list_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        # An item inside a block list, e.g. sources entries.
        if line.lstrip().startswith("-") and current_list_key:
            data.setdefault(current_list_key, [])
            if isinstance(data[current_list_key], list):
                data[current_list_key].append(line.lstrip()[1:].strip())
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if not value:
            current_list_key = key
            data[key] = []
            continue
        current_list_key = None
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            items = []
            if inner:
                for part in re.split(r",(?![^\[]*\])", inner):
                    items.append(part.strip().strip("\"'"))
            data[key] = items
        else:
            data[key] = value.strip().strip("\"'")
    return data, body


def count_sources(text: str) -> int:
    """Count ``url:`` lines inside the frontmatter sources block."""
    if not text.startswith("---"):
        return 0
    end = text.find("\n---", 3)
    head = text[3 : end if end != -1 else len(text)]
    return len(re.findall(r"^\s+-?\s*url:", head, re.MULTILINE))


def record_post(conn: sqlite3.Connection, md_path: Path) -> dict:
    """Upsert one markdown post into the coverage table."""
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    post_id = md_path.stem
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    conn.execute(
        """
        INSERT INTO posts (id, title, pub_date, domain, topic, confidence,
                           description, body_chars, source_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, pub_date=excluded.pub_date,
            domain=excluded.domain, topic=excluded.topic,
            confidence=excluded.confidence, description=excluded.description,
            body_chars=excluded.body_chars, source_count=excluded.source_count
        """,
        (
            post_id,
            fm.get("title", post_id),
            str(fm.get("pubDate", date.today().isoformat()))[:10],
            fm.get("domain", "ai"),
            fm.get("topic"),
            fm.get("confidence", "medium"),
            fm.get("description", ""),
            len(body),
            count_sources(text),
            now_iso(),
        ),
    )
    conn.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
    for tag in tags:
        if tag:
            conn.execute(
                "INSERT OR IGNORE INTO post_tags (post_id, tag) VALUES (?, ?)",
                (post_id, tag.strip().lower()),
            )
    # Writing about a topic retires the matching candidate.
    if fm.get("topic"):
        conn.execute(
            "UPDATE candidates SET status='used', used_at=? WHERE topic=? AND status!='used'",
            (now_iso(), fm["topic"]),
        )
    conn.commit()
    return {"recorded": post_id, "tags": tags, "sources": count_sources(text)}


def sync_all_posts(conn: sqlite3.Connection) -> dict:
    """Rebuild coverage from disk. Safe to re-run; disk is the source of truth."""
    if not POSTS_DIR.exists():
        return {"synced": 0}
    n = 0
    for md in sorted(POSTS_DIR.glob("*.md")):
        record_post(conn, md)
        n += 1
    return {"synced": n}


def profile(conn: sqlite3.Connection) -> dict:
    """Aggregate explicit feedback into per-subject affinity scores."""
    rows = conn.execute(
        """
        SELECT subject, SUM(weight) AS score, COUNT(*) AS n,
               MAX(created_at) AS last_at
        FROM feedback GROUP BY subject ORDER BY score DESC
        """
    ).fetchall()
    likes = [dict(r) for r in rows if r["score"] > 0]
    dislikes = [dict(r) for r in rows if r["score"] < 0]
    notes = conn.execute(
        "SELECT subject, signal, note, created_at FROM feedback "
        "WHERE note IS NOT NULL AND note != '' ORDER BY id DESC LIMIT 10"
    ).fetchall()
    return {
        "prefers": likes,
        "avoids": dislikes,
        "recent_notes": [dict(r) for r in notes],
    }


def brief(conn: sqlite3.Connection, days: int = 14) -> dict:
    """The context block the daily job reads before choosing what to write."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    recent = conn.execute(
        "SELECT id, title, pub_date, domain, topic, confidence FROM posts "
        "WHERE pub_date >= ? ORDER BY pub_date DESC",
        (cutoff,),
    ).fetchall()
    tag_rows = conn.execute(
        """
        SELECT t.tag, COUNT(*) AS n, MAX(p.pub_date) AS last_seen
        FROM post_tags t JOIN posts p ON p.id = t.post_id
        GROUP BY t.tag ORDER BY n DESC LIMIT 25
        """
    ).fetchall()
    domain_rows = conn.execute(
        "SELECT domain, COUNT(*) AS n, MAX(pub_date) AS last_seen "
        "FROM posts GROUP BY domain ORDER BY n DESC"
    ).fetchall()
    open_cands = conn.execute(
        "SELECT id, topic, domain, why, source_url, score FROM candidates "
        "WHERE status='open' ORDER BY score DESC, id ASC LIMIT 12"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]

    # Which domains are starved: the reader asked for AI/computing emphasis,
    # so surface staleness rather than raw counts.
    today = date.today()
    staleness = {}
    for row in domain_rows:
        try:
            gap = (today - date.fromisoformat(row["last_seen"])).days
        except (TypeError, ValueError):
            gap = 999
        staleness[row["domain"]] = gap

    return {
        "total_posts": total,
        "window_days": days,
        "recent_posts": [dict(r) for r in recent],
        "recent_titles": [r["title"] for r in recent],
        "top_tags": [dict(r) for r in tag_rows],
        "domain_mix": [dict(r) for r in domain_rows],
        "days_since_domain": staleness,
        "open_candidates": [dict(r) for r in open_cands],
        "reader": profile(conn),
    }


def suggest(conn: sqlite3.Connection, limit: int = 8) -> dict:
    """Rank open candidates: stored score, reader affinity, domain staleness."""
    prof = profile(conn)
    affinity: dict[str, float] = {}
    for item in prof["prefers"] + prof["avoids"]:
        affinity[item["subject"].lower()] = float(item["score"])

    today = date.today()
    domain_gap: dict[str, int] = {}
    for row in conn.execute(
        "SELECT domain, MAX(pub_date) AS last_seen FROM posts GROUP BY domain"
    ):
        try:
            domain_gap[row["domain"]] = (today - date.fromisoformat(row["last_seen"])).days
        except (TypeError, ValueError):
            domain_gap[row["domain"]] = 999

    scored = []
    for row in conn.execute(
        "SELECT id, topic, domain, why, source_url, score FROM candidates WHERE status='open'"
    ):
        text = f"{row['topic']} {row['domain']}".lower()
        bonus = sum(w for subj, w in affinity.items() if subj and subj in text)
        # A domain untouched for a week gets a nudge, capped so it cannot
        # dominate an explicitly requested topic.
        gap_bonus = min(domain_gap.get(row["domain"], 7), 14) / 14.0
        scored.append(
            {
                **dict(row),
                "rank_score": round(float(row["score"]) + bonus + gap_bonus, 3),
                "affinity_bonus": round(bonus, 3),
                "staleness_bonus": round(gap_bonus, 3),
            }
        )
    scored.sort(key=lambda r: r["rank_score"], reverse=True)
    return {"suggestions": scored[:limit], "considered": len(scored)}


def covered(conn: sqlite3.Connection, query: str) -> dict:
    """Has this ground been walked already? Checked before committing to a topic."""
    like = f"%{query.strip().lower()}%"
    rows = conn.execute(
        """
        SELECT id, title, pub_date, domain, topic FROM posts
        WHERE lower(title) LIKE ? OR lower(COALESCE(topic,'')) LIKE ?
           OR lower(COALESCE(description,'')) LIKE ?
           OR id IN (SELECT post_id FROM post_tags WHERE tag LIKE ?)
        ORDER BY pub_date DESC LIMIT 10
        """,
        (like, like, like, like),
    ).fetchall()
    return {"query": query, "hits": [dict(r) for r in rows], "covered": bool(rows)}


def add_candidate(conn, topic, domain="ai", why=None, source=None, score=0.5) -> dict:
    """Queue a topic. Re-adding an existing one raises its score instead of
    duplicating, so repeated sightings act as votes."""
    conn.execute(
        """
        INSERT INTO candidates (topic, domain, why, source_url, score, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(topic) DO UPDATE SET
            score = MIN(candidates.score + 0.25, 5.0),
            why = COALESCE(excluded.why, candidates.why),
            source_url = COALESCE(excluded.source_url, candidates.source_url)
        """,
        (topic.strip(), domain, why, source, float(score), now_iso()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, topic, domain, score, status FROM candidates WHERE topic=?",
        (topic.strip(),),
    ).fetchone()
    return dict(row)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reader model for the daily blog")
    ap.add_argument("--db", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("sync")
    sub.add_parser("profile")

    p = sub.add_parser("record-post")
    p.add_argument("path", type=Path)

    p = sub.add_parser("brief")
    p.add_argument("--days", type=int, default=14)

    p = sub.add_parser("suggest")
    p.add_argument("--limit", type=int, default=8)

    p = sub.add_parser("add-candidate")
    p.add_argument("topic")
    p.add_argument("--domain", default="ai")
    p.add_argument("--why")
    p.add_argument("--source")
    p.add_argument("--score", type=float, default=0.5)

    p = sub.add_parser("claim-candidate")
    p.add_argument("id", type=int)

    p = sub.add_parser("feedback")
    p.add_argument("subject")
    p.add_argument("--signal", required=True, choices=sorted(SIGNAL_WEIGHTS))
    p.add_argument("--note")

    p = sub.add_parser("covered")
    p.add_argument("query")

    args = ap.parse_args(argv)
    conn = connect(args.db)

    if args.cmd == "init":
        out = {"db": str(args.db or DEFAULT_DB), **sync_all_posts(conn)}
    elif args.cmd == "sync":
        out = sync_all_posts(conn)
    elif args.cmd == "record-post":
        out = record_post(conn, args.path)
    elif args.cmd == "brief":
        out = brief(conn, args.days)
    elif args.cmd == "suggest":
        out = suggest(conn, args.limit)
    elif args.cmd == "add-candidate":
        out = add_candidate(conn, args.topic, args.domain, args.why, args.source, args.score)
    elif args.cmd == "claim-candidate":
        conn.execute(
            "UPDATE candidates SET status='claimed' WHERE id=?", (args.id,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, topic, status FROM candidates WHERE id=?", (args.id,)
        ).fetchone()
        out = dict(row) if row else {"error": f"no candidate {args.id}"}
    elif args.cmd == "feedback":
        conn.execute(
            "INSERT INTO feedback (subject, signal, weight, note, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                args.subject.strip().lower(),
                args.signal,
                SIGNAL_WEIGHTS[args.signal],
                args.note,
                now_iso(),
            ),
        )
        conn.commit()
        out = {"recorded": args.subject, "signal": args.signal, **profile(conn)}
    elif args.cmd == "profile":
        out = profile(conn)
    elif args.cmd == "covered":
        out = covered(conn, args.query)
    else:  # pragma: no cover - argparse rejects unknown commands
        return 2

    json.dump(out, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
