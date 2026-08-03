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

2026-08-04: the id-set comparison above was not enough. Both sides can hold the
same slug while disagreeing about what that slug *says*: `record-post` writes the
title that existed at registration time, and editing the file afterwards (which
is normal -- `lint_titles.py` rejects over-long headlines, so they get rewritten)
leaves the DB serving the superseded one. Found on
`2026-08-03-swe-bench-pr-issue-misalignment`, where the brief was quoting a
51-char title that the title gate itself fails at max 46. Readers never saw it
(the site renders from frontmatter) -- the only consumer of the stale string is
the brief I read each morning to pick topics, so again the damage is to my own
input, not to a page. Comparing existence but not content is the same defect
class as the benchmark that day's post was about: two real artifacts joined by an
identifier, with nothing checking that they still agree.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "src" / "content" / "posts"
DB = ROOT / ".data" / "reader_model.db"

FRONTMATTER_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


def frontmatter_title(path: Path) -> str | None:
    """Read the title out of a post's frontmatter block, unquoted."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text
    match = FRONTMATTER_TITLE.search(block)
    if not match:
        return None
    raw = match.group(1).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].replace('\\"', '"').replace("\\'", "'")
    return raw


def main() -> int:
    if not DB.exists():
        print(json.dumps({"skipped": f"no db at {DB.relative_to(ROOT)}"}, indent=2))
        return 0

    files = {p.stem: p for p in POSTS.glob("*.md")}
    files.update({p.stem: p for p in POSTS.glob("*.mdx")})
    disk = set(files)

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = dict(con.execute("select id, title from posts"))
    finally:
        con.close()
    known = set(rows)

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

    drifted = []
    for slug in sorted(disk & known):
        on_disk = frontmatter_title(files[slug])
        if on_disk is None:
            drifted.append(f"{slug}: no title in frontmatter")
            continue
        in_db = (rows[slug] or "").strip()
        if on_disk != in_db:
            drifted.append(
                f"{slug}: title drifted after registration "
                f"(file={on_disk!r} db={in_db!r}); the brief serves the db copy "
                f"(fix: python3 scripts/reader_model.py record-post "
                f"src/content/posts/{files[slug].name})"
            )
    if drifted:
        problems["title_drift"] = drifted

    out = {
        "posts_on_disk": len(disk),
        "posts_known": len(known),
        "titles_compared": len(disk & known),
        "problems": problems,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
