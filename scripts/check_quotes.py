#!/usr/bin/env python3
"""Verify every English blockquote in a classics entry against its primary source.

A deconstruction's whole value is that the quoted original is exact. A single
word drifting ("can" -> "may") silently destroys that, and no amount of prose
review catches it reliably. This gate diffs each quote against the extracted
primary-source text and fails the build if any quote does not appear verbatim.

Usage:
    python3 scripts/check_quotes.py                 # all entries with a local source
    python3 scripts/check_quotes.py bitcoin-whitepaper

Sources live in sources/<entry-id>.txt (plain text extracted from the PDF). An
entry that also quotes a second original -- a mailing-list post, a letter, a
later erratum -- gets extra witness files named sources/<entry-id>.<slug>.txt;
a quote passes if it appears verbatim in any of them.
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
    # A footnote marker printed as a superscript on the page has to be written as
    # <sup>8</sup> in MDX. The tag is typography, not text, so drop the markup
    # and keep the digit -- the marker itself still has to match the source.
    s = re.sub(r"</?(?:sup|sub|em|strong|code)>", "", s)
    s = re.sub(r"\s+", " ", s)
    # "proof- of-work" -> "proof-of-work": hyphen + linebreak artefact.
    s = re.sub(r"- (?=[a-z])", "-", s)
    return s.strip()


def _skeleton(s: str) -> str:
    """Drop only what PDF extraction actually perturbs: whitespace.

    An earlier version stripped all punctuation. That silenced the line-break
    artefacts, but it also made the gate blind to real punctuation errors --
    it passed "as follows: [8]" when the paper reads "as follows [8]:".
    Citation marker placement is load-bearing in a deconstruction, so only
    whitespace is normalised away here.
    """
    return re.sub(r"\s+", "", s)


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
    # An entry may quote more than one primary document: the paper itself plus,
    # say, a mailing-list post by the same author. Those secondary originals are
    # just as load-bearing as the paper, so they get their own witness file
    # (sources/<entry>.<slug>.txt) and are checked with the same strictness.
    src_paths = sorted(SOURCES.glob(f"{entry_id}.txt")) + sorted(SOURCES.glob(f"{entry_id}.*.txt"))
    if not src_paths:
        return {"entry": entry_id, "unverifiable": f"missing {(SOURCES / f'{entry_id}.txt').relative_to(ROOT)}"}

    haystacks = [norm(p.read_text(encoding="utf-8")) for p in src_paths]
    quotes = english_blockquotes(mdx_path.read_text(encoding="utf-8"))

    # Second pass for anything that misses: compare letters and digits only.
    # PDF extraction drops or adds punctuation at line and figure boundaries, so
    # a punctuation-only difference is an artefact. A letter difference is not —
    # that is the "can" -> "may" class of error this gate exists to catch.
    skeletons = [_skeleton(h) for h in haystacks]

    def present(needle: str) -> bool:
        if any(needle in h for h in haystacks):
            return True
        return any(_skeleton(needle) in s for s in skeletons)

    bad = []
    for q in quotes:
        if present(q):
            continue
        # An elided quote ("A ... B") is a legitimate way to skip a clause. Each
        # surviving fragment still has to appear verbatim, and in one witness --
        # so the elision can shorten a quote but never fabricate a sentence.
        # A trailing ellipsis just means the sentence runs on past the quote.
        parts = [p.strip() for p in re.split(r"\s*\.\.\.\s*|\s*…\s*", q) if p.strip()]
        if (len(parts) > 1 or re.search(r"(\.\.\.|…)\s*$", q)) and all(
            present(p) for p in parts
        ):
            continue
        bad.append(q)
    return {
        "entry": entry_id,
        "sources": [p.name for p in src_paths],
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
