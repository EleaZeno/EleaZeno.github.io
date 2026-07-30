#!/usr/bin/env python3
"""Extract a checkable plain-text witness from a primary-source PDF.

    python3 scripts/extract_source.py <pdf> <entry-id> [--expect-sha256 HEX]

Writes sources/<entry-id>.txt for check_quotes.py to compare against.

Why this is a script and not a one-liner: PDF text extraction damages text in
ways that are invisible until a quote gate fails, and each fix has to be a
*faithful* restoration of the page rather than a loosening of the comparison.
Two classes are handled here.

1. Hyphenation. A word broken across a line ("appro-\nximately") extracts with
   the hyphen retained. Collapsing whitespace first turns it into "appro-
   ximately", so the join must happen before whitespace normalisation.

2. TeX math fonts with no usable ToUnicode map. Shannon 1948 is typeset in
   Computer Modern; its math glyphs extract as C0 control bytes -- 0x00 for the
   minus sign, 0x14 for <=, 0x19 for pi. Left alone they corrupt any quote that
   touches an inline formula. The map below is the standard OT1/CM encoding,
   applied only to characters that cannot legitimately appear in extracted prose.

Only ever restore what the page actually shows. If a glyph's identity is
uncertain, leave it and let the gate fail loudly instead of guessing.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Computer Modern math/symbol glyphs that extract as C0 control bytes.
CM_CONTROL_MAP = {
    "\x00": "\u2212",  # minus
    "\x01": "\u00b7",  # centred dot (also used in ".1" axis labels)
    "\x0b": "\u03b1",  # alpha
    "\x0c": "|",       # vertical bar / determinant rule
    "\r": "\u03b3",    # gamma
    "\x0e": "\u03b4",  # delta
    "\x0f": "\u03b5",  # epsilon
    "\x10": "\u03b7",  # eta
    "\x11": "\u03b8",  # theta
    "\x12": "\u03bb",  # lambda
    "\x13": "\u03bc",  # mu
    "\x14": "\u2264",  # <=
    "\x15": "\u2265",  # >=
    "\x16": "\u03bd",  # nu
    "\x17": "\u03be",  # xi
    "\x19": "\u03c0",  # pi
    "\x1a": "\u03c1",  # rho
    "\x1b": "\u03c3",  # sigma
    "\x1c": "\u03c4",  # tau
}


def strip_furniture(text: str, patterns: list[str]) -> str:
    """Drop running heads, folios and typesetter marks.

    A sentence that spans a page break extracts with the page furniture spliced
    into its middle ("...in the same\\n58\\nPsychology and the Real World\\nCH05.qxp
    ...room leads to"), which no amount of quote normalisation can repair. Only
    whole lines are removed, so body text is never touched.
    """
    if not patterns:
        return text
    rx = re.compile("|".join(patterns))
    kept = [ln for ln in text.split("\n") if not rx.fullmatch(ln.strip())]
    # Drop blank lines the removal leaves behind: a word hyphenated across the
    # page break ("op-\n<folio>\nposite") must end up adjacent again, or the
    # de-hyphenation below cannot see it.
    return "\n".join(ln for ln in kept if ln.strip())


def clean(text: str) -> tuple[str, list[str]]:
    # Join words hyphenated across a line break. Must run before whitespace
    # collapsing, otherwise the newline is already a space and the hyphen looks
    # like a real one ("proof-of-work").
    # "appro-\nximately" -> "approximately", but leave "how-\nto-study" alone:
    # when the continuation itself carries a hyphen the dash is real, not a
    # line-break artefact, and deleting it yields "howto-study".
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z]+(?:[^\w-]|$))", "", text)
    for bad, good in CM_CONTROL_MAP.items():
        text = text.replace(bad, good)
    # Anything still in C0 apart from tab/newline is an unmapped glyph.
    leftover = sorted({c for c in text if ord(c) < 32 and c not in "\n\t"})
    return text, leftover


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("entry_id")
    ap.add_argument("--expect-sha256")
    ap.add_argument(
        "--strip-line",
        action="append",
        default=[],
        metavar="REGEX",
        help="drop lines fully matching REGEX (running heads, page numbers). "
             "Repeatable. Use when a quote spanning a page break fails the gate.",
    )
    args = ap.parse_args()

    pdf = Path(args.pdf)
    blob = pdf.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if args.expect_sha256 and digest != args.expect_sha256:
        print(f"checksum mismatch\n  expected {args.expect_sha256}\n  got      {digest}", file=sys.stderr)
        return 2

    import fitz  # PyMuPDF

    doc = fitz.open(pdf)
    raw = "\n".join(page.get_text() for page in doc)
    raw = strip_furniture(raw, args.strip_line)
    text, leftover = clean(raw)

    out = ROOT / "sources" / f"{args.entry_id}.txt"
    out.write_text(text, encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {doc.page_count} pages, {len(text)} chars")
    print(f"sha256({pdf.name}) = {digest}")
    if leftover:
        print(f"warning: {len(leftover)} unmapped control glyphs remain: "
              f"{[hex(ord(c)) for c in leftover]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
