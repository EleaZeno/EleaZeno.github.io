#!/usr/bin/env python3
"""Assert that markdown emphasis actually rendered in dist/.

Why this gate exists
--------------------
Every other gate reads *source* text. None of them can tell whether a
`**bold**` span actually became a `<strong>` in the built page. CommonMark's
right-flanking rule refuses to close an emphasis run when the closing `**` is
preceded by punctuation and followed by a non-space, non-punctuation
character. In Chinese that is the *normal* way to write a bold lead-in:

    **猜测一：模型太大。**那换个小的。
                      ^^ preceded by 。 followed by 那  -> does not close

The `**` then survives into the HTML as a literal asterisk pair. On
2026-08-02 this shipped 25 visible `**` across two posts and two concept
pages while the whole gate chain was green.

This gate scans the built HTML for leftover emphasis delimiters, which is the
only place the truth is observable.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# Strip regions where a literal ** is legitimate: code blocks and inline code.
CODE = re.compile(r"<pre[\s\S]*?</pre>|<code[\s\S]*?</code>", re.I)
# Also strip KaTeX output: TeX source is kept in annotation/mathml and may
# legitimately contain ** (e.g. exponent stacks written by authors).
KATEX = re.compile(r"<annotation[\s\S]*?</annotation>|<math[\s\S]*?</math>", re.I)
BODY = re.compile(r"<main[\s\S]*?</main>", re.I)

DELIMS = (("**", "bold"), ("__", "bold"))


def offenders(html: str) -> list[dict]:
    m = BODY.search(html)
    text = m.group(0) if m else html
    text = KATEX.sub(" ", text)
    text = CODE.sub(" ", text)
    out = []
    for delim, kind in DELIMS:
        for hit in re.finditer(re.escape(delim), text):
            start = max(0, hit.start() - 45)
            ctx = re.sub(r"<[^>]+>", "", text[start : hit.end() + 45])
            ctx = " ".join(ctx.split())
            out.append({"delim": delim, "kind": kind, "context": ctx})
    return out


def main() -> int:
    if not DIST.exists():
        print(json.dumps({"error": "dist/ missing; run npm run build first"}))
        return 1
    problems: dict[str, list[dict]] = {}
    pages = 0
    for page in sorted(DIST.rglob("index.html")):
        pages += 1
        bad = offenders(page.read_text(errors="ignore"))
        if bad:
            rel = str(page.relative_to(DIST).parent) or "."
            problems[rel] = bad[:6]
    report = {
        "pages_scanned": pages,
        "pages_with_unrendered_emphasis": len(problems),
        "problems": problems,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
