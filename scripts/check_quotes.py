#!/usr/bin/env python3
"""Verify every English blockquote in a classics entry against its primary source.

A deconstruction's whole value is that the quoted original is exact. A single
word drifting ("can" -> "may") silently destroys that, and no amount of prose
review catches it reliably. This gate diffs each quote against the extracted
primary-source text and fails the build if any quote does not appear verbatim.

Usage:
    python3 scripts/check_quotes.py                 # all entries with a local source
    python3 scripts/check_quotes.py bitcoin-whitepaper

Sources live in sources/<entry-id>.txt (plain text extracted from the PDF).
Entries with no local source file are reported as unverifiable, not as failures,
so the gate stays honest about what it actually checked.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASSICS = ROOT / "src" / "content" / "classics"
SOURCES = ROOT / "sources"

# PDF extraction breaks words across lines and varies quote glyphs; neither is a
# real textual difference, so normalise both sides the same way before comparing.
_QUOTE_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for a, b in _QUOTE_MAP.items():
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    # "proof- of-work" -> "proof-of-work": hyphen + linebreak artefact.
    s = re.sub(r"- (?=[a-z])", "-", s)
    return s.strip()


def _skeleton(s: str) -> str:
    """Letters and digits only, lowercased — punctuation and spacing dropped."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def english_blockquotes(mdx: str) -> list[str]:
    """Contiguous '>' lines, kept only if they look like quoted English prose."""
    blocks: list[str] = []
    cur: list[str] = []
    for line in mdx.split("\n"):
        if line.startswith(">"):
            cur.append(line.lstrip(">").strip())
        elif cur:
            blocks.append(" ".join(cur))
            cur = []
    if cur:
        blocks.append(" ".join(cur))

    out = []
    for b in blocks:
        nb = norm(b)
        if len(nb) < 40:
            continue
        letters = sum(c.isascii() and c.isalpha() for c in nb)
        if letters / max(len(nb), 1) < 0.55:
            continue  # Chinese commentary, not a quote
        out.append(nb)
    return out


def check(entry_id: str) -> dict:
    mdx_path = next((p for p in CLASSICS.glob(f"{entry_id}.*")), None)
    if mdx_path is None:
        return {"entry": entry_id, "error": "no such entry"}
    src_path = SOURCES / f"{entry_id}.txt"
    if not src_path.exists():
        return {"entry": entry_id, "unverifiable": f"missing {src_path.relative_to(ROOT)}"}

    raw_src = src_path.read_text(encoding="utf-8")
    haystack = norm(raw_src)
    quotes = english_blockquotes(mdx_path.read_text(encoding="utf-8"))

    # Second pass for anything that misses: compare letters and digits only.
    # PDF extraction drops or adds punctuation at line and figure boundaries, so
    # a punctuation-only difference is an artefact. A letter difference is not —
    # that is the "can" -> "may" class of error this gate exists to catch.
    skeleton = _skeleton(haystack)
    bad = []
    for q in quotes:
        if q in haystack:
            continue
        if _skeleton(q) in skeleton:
            continue
        bad.append(q)
    return {
        "entry": entry_id,
        "quotes_checked": len(quotes),
        "failing": [{"quote": q[:180], "chars": len(q)} for q in bad],
    }


def main() -> int:
    ids = sys.argv[1:] or sorted(p.stem for p in CLASSICS.glob("*.md*"))
    results = [check(i) for i in ids]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(r.get("failing") or r.get("error") for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
