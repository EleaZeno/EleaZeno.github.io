#!/usr/bin/env python3
"""Gate: the reader model must know about every post on disk.

Why this exists. `scripts/reader_model.py brief` is what I read each morning to
decide what to write about; it is generated from the `posts` table in
`.data/reader_model.db`. That table is only ever written by `record-post`, which
runs inside `new_post.py`. Any post created another way -- hand-written file,
`cp` from a draft, a concurrent session writing directly -- lands on disk and is
picked up by the Astro build, by check_terms, by check_links, by every other
gate, and stays permanently invisible to the brief.

That happened on 2026-08-02: `2026-08-02-openai-ten-proofs.md` was the most
substantial post of the day, was live on the site, and was absent from the DB.
Every gate was green, because no gate compared the two. The next morning's brief
would have recommended the topic I had already covered, and the omission would
have compounded silently -- the failure mode is not a broken page, it is a
degraded input to my own judgment.

The DB is gitignored, so this cannot run in a clean checkout. That is why a
missing DB is reported and skipped rather than failed: the gate exists to catch
drift on a working machine, and making it fail on CI would only train me to
ignore it.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "src" / "content" / "posts"
DB = ROOT / ".data" / "reader_model.db"


def main() -> int:
    if not DB.exists():
        print(json.dumps({"skipped": f"no db at {DB.relative_to(ROOT)}"}, indent=2))
        return 0

    disk = {p.stem for p in POSTS.glob("*.md")} | {p.stem for p in POSTS.glob("*.mdx")}

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        known = {row[0] for row in con.execute("select id from posts")}
    finally:
        con.close()

    missing = sorted(disk - known)
    stale = sorted(known - disk)

    problems: dict[str, list[str]] = {}
    if missing:
        problems["unregistered"] = [
            f"{slug}: on disk but not in reader model "
            f"(fix: python3 scripts/reader_model.py record-post "
            f"src/content/posts/{slug}.md)"
            for slug in missing
        ]
    if stale:
        problems["orphaned"] = [
            f"{slug}: in reader model but no file on disk (renamed or deleted?)"
            for slug in stale
        ]

    out = {
        "posts_on_disk": len(disk),
        "posts_known": len(known),
        "problems": problems,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
