#!/usr/bin/env python3
"""Write one nightly reflection file.

Hermes has no built-in dreaming; this is the storage half of a self-built
version. Kept deliberately separate from posts: dreams are dated, short, and
allowed to be wrong. Nothing here is fact-checked or cited, and the site says
so.

Usage:
    new_dream.py --body-file /tmp/dream.md [--seed "what set it off"]
        [--cycle 1] [--date YYYY-MM-DD] [--generated-by model]
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


def q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write one nightly reflection")
    ap.add_argument("--body-file", type=Path, required=True)
    ap.add_argument("--seed")
    ap.add_argument("--cycle", type=int, default=1)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--generated-by", default="")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise SystemExit(f"--date must be YYYY-MM-DD, got {args.date!r}")
    if args.cycle < 1:
        raise SystemExit("--cycle starts at 1")

    body = args.body_file.read_text(encoding="utf-8").strip()
    if len(body) < 120:
        raise SystemExit(f"dream is only {len(body)} chars — say something real or skip")

    DREAMS.mkdir(parents=True, exist_ok=True)
    path = DREAMS / f"{args.date}-c{args.cycle}.md"
    # Cycles within one night are additive; find the next free slot instead of
    # clobbering an earlier reflection.
    cycle = args.cycle
    while path.exists():
        cycle += 1
        path = DREAMS / f"{args.date}-c{cycle}.md"

    lines = ["---", f"date: {args.date}", f"cycle: {cycle}"]
    if args.seed:
        lines.append(f"seed: {q(args.seed)}")
    if args.generated_by:
        lines.append(f"generatedBy: {q(args.generated_by)}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n\n" + body + "\n", encoding="utf-8")

    json.dump(
        {"path": str(path.relative_to(REPO)), "cycle": cycle, "chars": len(body)},
        sys.stdout, ensure_ascii=False, indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
