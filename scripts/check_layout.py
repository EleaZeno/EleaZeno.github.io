#!/usr/bin/env python3
"""
Verify the reading column stays readable at every viewport width.

Why this gate exists
--------------------
check_terms / check_links / check_wiki / lint_titles all read *text*. astro
check and astro build only prove the site *compiles*. None of them look at
geometry, so a purely visual defect passed every gate: `.prose` reserved an
18.5rem right margin for sidenotes on every page, including the ones with no
sidenotes, leaving dreams and posts with text squeezed into the left 40rem and
a permanently empty strip beside it. A second bug hid in the same blind spot:
the 76rem..66rem band sized the column `1fr`, so narrowing the window made
lines *longer* (640px at 1440px, 892px at 1200px).

How it works
------------
It resolves the actual CSS: it parses `grid-template-columns` off the real
`.layout` rules (including inside media queries) and the real `padding-right`
off the `.prose` rules, then evaluates them per viewport width. Nothing about
the band structure is hardcoded, so editing the CSS moves this gate with it and
reintroducing either bug fails the check.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
GLOBAL_CSS = ROOT / "src" / "styles" / "global.css"
TOKENS_CSS = ROOT / "src" / "styles" / "tokens.css"

# Readable-line bounds. The upper bound is generous (CJK tolerates longer lines
# than Latin) but finite; the point is catching runaway columns, not policing
# typography to the pixel.
# Lower bound on the text column. A fixed floor is wrong across viewports: a
# 390px phone physically cannot host 26rem (416px) of text, so judging it by the
# desktop floor reports a defect that no CSS change could fix. What actually
# matters on a phone is that the shell is not eating the screen -- the column
# should get nearly all of the viewport.
MIN_REM = 26.0
# Below this viewport, assert the column claims at least this fraction of the
# screen instead of an absolute rem floor.
NARROW_PX = 700
MIN_VIEWPORT_FRACTION = 0.86
MAX_REM = 50.0
REM_PX = 16.0

# Phone widths matter as much as desktop: the reported unreadable page was seen
# on iPhone Safari. 390 = iPhone 14/15, 430 = 15 Pro Max, 360 = common Android,
# 320 = smallest still-supported viewport.
WIDTHS = [1920, 1600, 1440, 1366, 1280, 1216, 1200, 1100, 1044, 1024, 992, 900,
          820, 768, 700, 600, 540, 430, 414, 390, 375, 360, 320]


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def read_tokens() -> dict[str, float]:
    """Pull the rem-valued layout tokens out of tokens.css."""
    css = strip_comments(TOKENS_CSS.read_text(encoding="utf-8"))
    return {n: float(v) for n, v in re.findall(r"--([a-z0-9-]+):\s*([0-9.]+)rem\s*;", css)}


def resolve(expr: str, tok: dict[str, float], fallback: float | None = None) -> float | None:
    """
    Evaluate a CSS length expression in rem: var(), calc(), bare rem numbers.

    Returns None for values that aren't a fixed length (1fr, auto, %), which is
    itself meaningful: an unbounded track is what caused the inversion bug.
    """
    e = expr.strip()
    if re.search(r"\d\s*fr\b|\bauto\b|%", e):
        return None
    for _ in range(10):
        new = re.sub(r"var\(\s*--([a-z0-9-]+)\s*(?:,[^)]*)?\)",
                     lambda m: repr(tok.get(m.group(1), 0.0)), e)
        if new == e:
            break
        e = new
    e = re.sub(r"calc\(", "(", e)
    e = re.sub(r"([0-9.]+)rem", r"\1", e)
    e = re.sub(r"([0-9.]+)px", lambda m: repr(float(m.group(1)) / REM_PX), e)
    if not re.fullmatch(r"[0-9.()+\-*/\s]+", e):
        return fallback
    # Parsed with ast in literal-arithmetic mode rather than eval'd: this input
    # comes from a stylesheet, and a numeric-only regex is not a safe substitute
    # for refusing to execute code.
    try:
        return float(_arith(ast.parse(e, mode="eval").body))
    except Exception:
        return fallback


_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
           ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


def _arith(node: ast.AST) -> float:
    """Evaluate a pure-arithmetic AST. Anything else raises."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _arith(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_arith(node.left), _arith(node.right))
    raise ValueError(f"unsupported expression node: {type(node).__name__}")


def parse_rules(css: str) -> list[tuple[float, str, str]]:
    """
    Flatten the stylesheet into (max_width_rem, selector, declarations).

    max_width_rem is inf for rules outside any max-width media query, so sorting
    by it and applying in document order reproduces the cascade for a given
    viewport.
    """
    css = strip_comments(css)
    out: list[tuple[float, str, str]] = []

    def walk(text: str, limit: float) -> None:
        i = 0
        while i < len(text):
            brace = text.find("{", i)
            if brace < 0:
                return
            prelude = text[i:brace].strip()
            depth, j = 0, brace
            while j < len(text):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            body = text[brace + 1:j]
            if prelude.startswith("@media"):
                m = re.search(r"max-width:\s*([0-9.]+)rem", prelude)
                inner = min(limit, float(m.group(1))) if m else limit
                if "min-width" in prelude and not m:
                    inner = limit  # min-width-only blocks don't cap the range
                walk(body, inner)
            elif prelude.startswith("@"):
                pass  # @supports/@font-face etc: not layout tracks
            else:
                out.append((limit, prelude, body))
            i = j + 1

    walk(css, float("inf"))
    return out


def decl(body: str, prop: str) -> str | None:
    m = None
    for m in re.finditer(rf"(?<![-\w]){re.escape(prop)}\s*:\s*([^;}}]+)", body):
        pass
    return m.group(1).strip() if m else None


def selector_matches(selector: str, has_notes: bool) -> bool:
    """Does any comma-part of this selector apply to our .layout element?"""
    for part in selector.split(","):
        p = part.strip()
        if not re.search(r"\.layout\b", p):
            continue
        if ".layout:not(.has-margin-notes)" in p:
            if not has_notes:
                return True
            continue
        if re.search(r"\.has-margin-notes\b.*\.layout|\.layout\.has-margin-notes", p):
            if has_notes:
                return True
            continue
        # plain .layout, possibly with descendants -- applies either way
        if re.fullmatch(r"\.layout(\s*>?\s*[\w.\-\[\]='\"]+)?", p) or p == ".layout":
            return True
    return False


def prose_selector_matches(selector: str, has_notes: bool) -> bool:
    for part in selector.split(","):
        p = part.strip()
        if not re.search(r"\.prose\b|\.classic-body\b", p):
            continue
        if ".has-margin-notes" in p:
            if has_notes:
                return True
            continue
        return True
    return False


def track_widths(value: str, tok: dict[str, float]) -> list[float | None]:
    """Split grid-template-columns into per-track resolved rem widths."""
    tracks, depth, cur = [], 0, ""
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == " " and depth == 0:
            if cur.strip():
                tracks.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        tracks.append(cur.strip())

    widths: list[float | None] = []
    for t in tracks:
        m = re.fullmatch(r"minmax\(\s*([^,]+),\s*(.+)\)", t)
        widths.append(resolve(m.group(2), tok) if m else resolve(t, tok))
    return widths


def text_column_rem(viewport_px: float, has_notes: bool, tok: dict[str, float],
                    rules: list[tuple[float, str, str]]) -> tuple[float, str, float]:
    """
    Resolve the rendered text column from the parsed CSS.

    Returns (text_width_rem, which_rule_won, reserved_margin_rem). The third
    value matters on its own: margin reserved on a page that renders no sidenote
    is dead space, which is a defect even when the remaining text is readable.
    """
    vw = viewport_px / REM_PX
    shell_max = tok.get("wide", vw)
    shell_pad = 0.0
    for limit, sel, body in rules:
        if vw <= limit and re.search(r"(^|,)\s*\.shell\b", sel):
            pad = decl(body, "padding")
            if pad:
                parts = pad.split()
                horiz = parts[1] if len(parts) > 1 else parts[0]
                v = resolve(horiz, tok)
                if v is not None:
                    shell_pad = v * 2
    shell = min(shell_max, vw) - shell_pad

    grid, origin = None, "default"
    for limit, sel, body in rules:
        if vw <= limit and selector_matches(sel, has_notes):
            g = decl(body, "grid-template-columns")
            if g:
                grid, origin = g, f"{sel} @<= {limit}"
    if grid is None:
        return shell, "no grid rule", 0.0

    tracks = track_widths(grid, tok)
    gap = 0.0
    for limit, sel, body in rules:
        if vw <= limit and selector_matches(sel, has_notes):
            for prop in ("column-gap", "gap"):
                g = decl(body, prop)
                if g:
                    v = resolve(g.split()[-1], tok)
                    if v is not None:
                        gap = v

    fixed = sum(t for t in tracks[:-1] if t is not None)
    available = shell - fixed - gap * max(0, len(tracks) - 1)
    last = tracks[-1]
    col = available if last is None else min(last, available)

    # Reserved sidenote margin comes out of the text column.
    pad_r = 0.0
    for limit, sel, body in rules:
        if vw <= limit and prose_selector_matches(sel, has_notes):
            p = decl(body, "padding-right")
            if p:
                v = resolve(p, tok)
                if v is not None:
                    pad_r = v
    return col - pad_r, origin, pad_r


def audit_dist() -> tuple[list[str], int, list[str]]:
    """Cross-check each built page's claimed margin against what it renders."""
    marked, plain, mismatches = [], 0, []
    if not DIST.exists():
        return marked, plain, mismatches
    for html in sorted(DIST.rglob("index.html")):
        text = html.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'class="layout([^"]*)"', text)
        if not m:
            continue
        page = str(html.parent.relative_to(DIST)) or "/"
        claims = "has-margin-notes" in m.group(1)
        renders = 'class="sidenote' in text
        if claims != renders:
            why = "claims margin, renders no sidenote" if claims else "renders sidenotes, no margin reserved"
            mismatches.append(f"{page}: {why}")
        if claims:
            marked.append(page)
        else:
            plain += 1
    return marked, plain, mismatches


def main() -> int:
    tok = read_tokens()
    rules = parse_rules(GLOBAL_CSS.read_text(encoding="utf-8"))
    problems: list[str] = []
    table = []

    for width in WIDTHS:
        row: dict[str, object] = {"viewport_px": width}
        for label, has in (("plain", False), ("sidenotes", True)):
            rem, origin, reserved = text_column_rem(width, has, tok, rules)
            row[label] = f"{rem:.2f}rem/{rem * REM_PX:.0f}px"
            if width >= NARROW_PX:
                if rem < MIN_REM:
                    problems.append(
                        f"{width}px {label}: column {rem:.2f}rem below {MIN_REM}rem [{origin}]")
            else:
                # Phone: the column cannot reach a desktop rem floor, so require
                # instead that the shell is not stealing the screen.
                frac = (rem * REM_PX) / width
                if frac < MIN_VIEWPORT_FRACTION:
                    problems.append(
                        f"{width}px {label}: column {rem * REM_PX:.0f}px is only "
                        f"{frac:.0%} of viewport (want >={MIN_VIEWPORT_FRACTION:.0%}) [{origin}]")
            if rem > MAX_REM:
                problems.append(f"{width}px {label}: column {rem:.2f}rem above {MAX_REM}rem [{origin}]")
            # The original defect: space reserved beside text that has no notes
            # to put there. Readable width alone does not catch it.
            if not has and reserved > 0.01:
                problems.append(
                    f"{width}px plain: {reserved:.2f}rem reserved for sidenotes on pages "
                    f"that have none — dead strip beside the text [{origin}]"
                )
        table.append(row)

    # Narrowing the viewport must never widen the text column.
    for label, has in (("plain", False), ("sidenotes", True)):
        ordered = sorted(WIDTHS, reverse=True)
        for wide_px, narrow_px in zip(ordered, ordered[1:]):
            w, _, _ = text_column_rem(wide_px, has, tok, rules)
            n, _, _ = text_column_rem(narrow_px, has, tok, rules)
            if n > w + 0.01:
                problems.append(
                    f"{label}: {narrow_px}px gives a WIDER column ({n:.2f}rem) than "
                    f"{wide_px}px ({w:.2f}rem) — responsive inversion"
                )

    marked, plain, mismatches = audit_dist()
    problems.extend(mismatches)

    print(json.dumps({
        "tokens_rem": tok,
        "columns": table,
        "pages_with_margin_notes": marked,
        "pages_plain": plain,
        "problems": problems,
    }, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
