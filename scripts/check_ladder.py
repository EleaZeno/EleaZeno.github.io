#!/usr/bin/env python3
"""Gate: every classics entry must climb the full ladder.

看懂 -> 学会 -> 记住 -> 会用. The first three are carried by prose, <Prereq>
and <Check>. The fourth is carried by <Apply>, and it is the one that silently
goes missing: nothing else in the build fails when a piece has no transfer
task, so it has to be checked here.

Thresholds are deliberately low -- this is a floor, not a style guide.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSICS = ROOT / "src" / "content" / "classics"

MIN_APPLY = 2
MIN_CHECK = 3


def main() -> int:
    problems: dict[str, list[str]] = {}
    stats: dict[str, dict[str, int]] = {}

    for path in sorted(CLASSICS.glob("*.mdx")):
        text = path.read_text(encoding="utf-8")
        name = path.stem
        n_apply = text.count("<Apply")
        n_check = text.count("<Check")
        stats[name] = {"apply": n_apply, "check": n_check}

        errs: list[str] = []
        if n_apply < MIN_APPLY:
            errs.append(f"only {n_apply} <Apply> (need >={MIN_APPLY}): no transfer step")
        if n_check < MIN_CHECK:
            errs.append(f"only {n_check} <Check> (need >={MIN_CHECK})")
        if n_apply and "import Apply" not in text:
            errs.append("<Apply> used without importing the component")
        if "[truncated]" in text:
            errs.append("literal [truncated] marker in source")
        if errs:
            problems[name] = errs

    out = {"classics": len(stats), "stats": stats, "problems": problems}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
