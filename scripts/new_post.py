#!/usr/bin/env python3
"""Create one post file with validated frontmatter, then record it.

Exists so the daily job never hand-writes YAML. Hand-written frontmatter is
where the silent failures live: an unquoted colon in a title, a source with a
bare URL and no name, a tag list that is a string instead of a list. This
validates first and writes second.

Usage:
    new_post.py --title "..." --body-file /tmp/body.md \
        [--domain ai|crypto|physics|bio|space|energy|compute|systems|theory|other] \
        [--confidence high|medium|exploratory] \
        [--tag t1 --tag t2] \
        [--source "Title|https://url|Outlet"] \
        [--take "markdown"] [--take-file /tmp/take.md] \
        [--topic "..."] [--date YYYY-MM-DD] [--slug custom-slug] \
        [--description "..."] [--draft] [--force]

Prints JSON: the path written plus what was recorded.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POSTS = REPO / "src" / "content" / "posts"
DOMAINS = (
    "ai", "crypto", "physics", "bio", "space", "energy",
    "compute", "systems", "theory", "other",
)
CONFIDENCE = ("high", "medium", "exploratory")

# Frontmatter needs double quotes around every string that might contain a
# colon; escape any embedded quote rather than switching quote styles.
def q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def slugify(title: str, fallback: str) -> str:
    """URL slug from the title.

    Latin text becomes a hyphenated ASCII slug. A pure-CJK title has no ASCII
    to keep, so rather than degrading to the date (which yields ids like
    ``2026-07-30-2026-07-30``) it keeps the CJK characters: Astro percent-
    encodes them in the route and browsers display them decoded.
    """
    norm = unicodedata.normalize("NFKC", title)
    ascii_slug = re.sub(r"[^a-zA-Z0-9]+", "-", norm.encode("ascii", "ignore").decode())
    words = [w for w in ascii_slug.strip("-").lower().split("-") if w]
    if words:
        return "-".join(words[:8])
    # Keep CJK/word characters, drop punctuation and whitespace.
    cjk = re.sub(r"[\s\u3000-\u303f\uff00-\uffef]+", "-", norm.strip())
    cjk = re.sub(r"[^\w\u4e00-\u9fff-]+", "", cjk).strip("-")
    cjk = re.sub(r"-{2,}", "-", cjk)
    return cjk[:24] if cjk else fallback


def parse_source(raw: str) -> dict:
    """``Title|url|Outlet`` -> dict. Outlet optional; title and url required."""
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise SystemExit(f"--source needs 'Title|https://url[|Outlet]', got: {raw!r}")
    title, url = parts[0], parts[1]
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"--source url must be absolute http(s), got: {url!r}")
    src = {"title": title, "url": url}
    if len(parts) > 2 and parts[2]:
        src["outlet"] = parts[2]
    return src


def first_sentence(body: str, limit: int = 120) -> str:
    """Fallback description: the first real sentence of the body."""
    text = re.sub(r"^#.*$", "", body, flags=re.MULTILINE)
    text = re.sub(r"[*`>\-\[\]]", "", text)
    text = " ".join(text.split())
    for sep in ("。", ". ", "！", "？"):
        if sep in text:
            head = text.split(sep)[0] + (sep.strip() or "")
            if len(head) > 12:
                return head[:limit]
    return text[:limit]


def build_frontmatter(meta: dict) -> str:
    lines = ["---"]
    lines.append(f"title: {q(meta['title'])}")
    lines.append(f"description: {q(meta['description'])}")
    lines.append(f"pubDate: {meta['date']}")
    lines.append(f"domain: {meta['domain']}")
    lines.append(f"confidence: {meta['confidence']}")
    tags = meta.get("tags") or []
    lines.append("tags: [" + ", ".join(q(t) for t in tags) + "]")
    if meta.get("topic"):
        lines.append(f"topic: {q(meta['topic'])}")
    if meta.get("generated_by"):
        lines.append(f"generatedBy: {q(meta['generated_by'])}")
    if meta.get("draft"):
        lines.append("draft: true")
    if meta.get("take"):
        # Block scalar keeps markdown (lists, links, blank lines) intact
        # without needing to escape anything.
        lines.append("take: |")
        for line in meta["take"].rstrip().splitlines():
            lines.append(f"  {line}" if line.strip() else "")
    sources = meta.get("sources") or []
    if sources:
        lines.append("sources:")
        for s in sources:
            lines.append(f"  - title: {q(s['title'])}")
            lines.append(f"    url: {q(s['url'])}")
            if s.get("outlet"):
                lines.append(f"    outlet: {q(s['outlet'])}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write one validated post file")
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", type=Path, required=True)
    ap.add_argument("--description")
    ap.add_argument("--domain", default="ai", choices=DOMAINS)
    ap.add_argument("--confidence", default="medium", choices=CONFIDENCE)
    ap.add_argument("--tag", action="append", dest="tags", default=[])
    ap.add_argument("--source", action="append", dest="sources", default=[])
    ap.add_argument("--take")
    ap.add_argument("--take-file", type=Path)
    ap.add_argument("--topic")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--slug")
    ap.add_argument("--generated-by", default="")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise SystemExit(f"--date must be YYYY-MM-DD, got {args.date!r}")

    body = args.body_file.read_text(encoding="utf-8").strip()
    if len(body) < 400:
        raise SystemExit(
            f"body is only {len(body)} chars — too short to publish. "
            "Write the real piece, or skip the day."
        )
    # A leading H1 duplicates the rendered title.
    body = re.sub(r"^#\s+.*\n+", "", body).strip()

    take = args.take
    if args.take_file:
        take = args.take_file.read_text(encoding="utf-8").strip()
    if not take:
        raise SystemExit(
            "--take is required: every post carries my own commentary. "
            "If there is genuinely nothing to add, the topic is not worth a post."
        )

    sources = [parse_source(s) for s in args.sources]
    seen, deduped = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            deduped.append(s)

    tags = []
    for t in args.tags:
        t = t.strip().lower()
        if t and t not in tags:
            tags.append(t)

    slug = args.slug or slugify(args.title, args.date)
    post_id = f"{args.date}-{slug}"
    path = POSTS / f"{post_id}.md"
    if path.exists() and not args.force:
        raise SystemExit(f"{path.name} already exists (pass --force to overwrite)")

    meta = {
        "title": args.title.strip(),
        "description": (args.description or first_sentence(body)).strip(),
        "date": args.date,
        "domain": args.domain,
        "confidence": args.confidence,
        "tags": tags,
        "topic": args.topic,
        "take": take,
        "sources": deduped,
        "generated_by": args.generated_by,
        "draft": args.draft,
    }

    POSTS.mkdir(parents=True, exist_ok=True)
    path.write_text(build_frontmatter(meta) + body + "\n", encoding="utf-8")

    rec = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "reader_model.py"), "record-post", str(path)],
        capture_output=True, text=True,
    )
    json.dump(
        {
            "path": str(path.relative_to(REPO)),
            "id": post_id,
            "chars": len(body),
            "sources": len(deduped),
            "tags": tags,
            "recorded": rec.returncode == 0,
        },
        sys.stdout, ensure_ascii=False, indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
