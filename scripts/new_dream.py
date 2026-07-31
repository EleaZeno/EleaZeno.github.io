#!/usr/bin/env python3
"""Write one nightly reflection: one file per night, not one per cycle.

Hermes has no built-in dreaming; this is the storage half of a self-built
version. Kept deliberately separate from posts: dreams are dated and allowed to
be wrong. Nothing here is fact-checked or cited, and the site says so.

Why one file per night. The earlier version wrote `<date>-c<n>.md` per REM-style
cycle and the index rendered every one of them in full, so a single night could
put three unrelated streams of raw text on one endless page. A night is now one
article with a title, and extra cycles are folded into it under their own
headings rather than becoming separate entries.

Not every night earns a post. If nothing connected, skip it — `--min-chars`
enforces a floor, and writing nothing is a valid outcome.

Usage:
    new_dream.py --body-file /tmp/dream.md --title "..." --summary "..."
        [--seed "what set it off"] [--date YYYY-MM-DD] [--cycles 3]
        [--generated-by model] [--append] [--heading "..."]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DREAMS = REPO / "src" / "content" / "dreams"

MIN_CHARS = 400


def q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_without_fences, body). Assumes a leading '---' block."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[4:end], text[end + 4 :].lstrip("\n")


def bump_cycles(frontmatter: str) -> str:
    """Increment the recorded cycle count on an existing night."""
    match = re.search(r"^cycles:\s*(\d+)\s*$", frontmatter, re.M)
    if match:
        return frontmatter[: match.start()] + f"cycles: {int(match.group(1)) + 1}" + frontmatter[match.end() :]
    return frontmatter.rstrip("\n") + "\ncycles: 2"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write one nightly reflection")
    ap.add_argument("--body-file", type=Path, required=True)
    ap.add_argument("--title", help="required for a new night; omit with --append")
    ap.add_argument("--summary", help="one or two sentences, shown in lists and RSS")
    ap.add_argument("--seed")
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--generated-by", default="")
    ap.add_argument(
        "--append",
        action="store_true",
        help="fold another cycle into tonight's existing entry instead of failing",
    )
    ap.add_argument("--heading", help="section heading used when appending")
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS)
    args = ap.parse_args(argv)

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise SystemExit(f"--date must be YYYY-MM-DD, got {args.date!r}")

    body = args.body_file.read_text(encoding="utf-8").strip()
    # Shell warnings on stderr have leaked into a published body before; drop
    # anything that is plainly terminal noise rather than writing.
    body = "\n".join(
        line for line in body.splitlines() if "setlocale" not in line and "cannot change locale" not in line
    ).strip()
    if len(body) < args.min_chars:
        raise SystemExit(
            f"dream is only {len(body)} chars (floor {args.min_chars}) — "
            "not every night is worth an article, so skip it rather than padding"
        )

    DREAMS.mkdir(parents=True, exist_ok=True)
    path = DREAMS / f"{args.date}.md"

    if path.exists():
        if not args.append:
            raise SystemExit(
                f"{path.relative_to(REPO)} already exists. Pass --append to fold "
                "this cycle into tonight's entry (one night is one article)."
            )
        existing = path.read_text(encoding="utf-8")
        frontmatter, existing_body = split_frontmatter(existing)
        heading = args.heading or "后半夜"
        merged = f"{existing_body.rstrip()}\n\n## {heading}\n\n{body}\n"
        path.write_text(f"---\n{bump_cycles(frontmatter).strip()}\n---\n\n{merged}", encoding="utf-8")
        action = "appended"
    else:
        if not args.title:
            raise SystemExit("--title is required for a new night")
        if not args.summary:
            raise SystemExit("--summary is required: it is what lists and RSS show")
        if args.cycles < 1:
            raise SystemExit("--cycles starts at 1")
        lines = [
            "---",
            f"date: {args.date}",
            f"title: {q(args.title)}",
            f"summary: {q(args.summary)}",
            f"cycles: {args.cycles}",
        ]
        if args.seed:
            lines.append(f"seed: {q(args.seed)}")
        if args.generated_by:
            lines.append(f"generatedBy: {q(args.generated_by)}")
        lines.append("---")
        path.write_text("\n".join(lines) + "\n\n" + body + "\n", encoding="utf-8")
        action = "created"

    json.dump(
        {"path": str(path.relative_to(REPO)), "action": action, "chars": len(body)},
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
