#!/usr/bin/env python3
"""Verify the built site: internal links resolve, citations are well-formed.

Catches the class of bug that only appears in production — a base-path prefix
dropped from an href, a tag route that 404s, a citation with a malformed URL.
Run after `npm run build`, before committing.

Exit 0 = clean, 1 = problems found (printed).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"


def internal_links(base: str) -> tuple[int, list[str]]:
    """Every internal href/src in the built HTML must map to a real file."""
    problems: list[str] = []
    checked = 0
    prefix = base if base.endswith("/") else base + "/"

    for html in DIST.rglob("*.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'(?:href|src)="([^"]+)"', text):
            href = m.group(1)
            if href.startswith(("http://", "https://", "#", "mailto:", "data:")):
                continue
            path = urllib.parse.urlparse(href).path
            if not path:
                continue
            checked += 1
            if not path.startswith(prefix) and path != base.rstrip("/"):
                problems.append(f"{html.relative_to(DIST)}: {href} missing base {prefix!r}")
                continue
            rel = urllib.parse.unquote(path[len(prefix):]).strip("/")
            if rel == "":
                continue
            target = DIST / rel
            if not (target.exists() or (DIST / (rel + ".html")).exists()
                    or (target / "index.html").exists()):
                problems.append(f"{html.relative_to(DIST)}: {href} -> missing {rel}")
    return checked, problems


def citations() -> tuple[int, list[str]]:
    """Citation links must be absolute and carry visible link text."""
    problems: list[str] = []
    count = 0
    for html in DIST.rglob("*.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        block = re.search(r'<section class="sources">(.*?)</section>', text, re.S)
        if not block:
            continue
        for m in re.finditer(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block.group(1), re.S):
            count += 1
            url, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not url.startswith(("http://", "https://")):
                problems.append(f"{html.relative_to(DIST)}: citation not absolute: {url}")
            if not label or label.startswith("http"):
                problems.append(f"{html.relative_to(DIST)}: citation lacks a title: {url}")
    return count, problems


def feed_and_meta(base: str) -> list[str]:
    """RSS item links and canonicals must carry the base path."""
    problems: list[str] = []
    rss = DIST / "rss.xml"
    if rss.exists():
        text = rss.read_text(encoding="utf-8")
        for link in re.findall(r"<link>(.*?)</link>", text):
            if not link.startswith("http"):
                problems.append(f"rss.xml: non-absolute link {link}")
            elif base != "/" and base.rstrip("/") not in link:
                problems.append(f"rss.xml: link missing base path: {link}")
    index = DIST / "index.html"
    if index.exists():
        text = index.read_text(encoding="utf-8")
        if 'rel="canonical"' not in text:
            problems.append("index.html: no canonical link")
    return problems


def main() -> int:
    if not DIST.exists():
        print("dist/ not found — run `npm run build` first", file=sys.stderr)
        return 1
    base = "/"
    cfg = REPO / "astro.config.mjs"
    # BASE_PATH is injected at build time; the built output is the source of
    # truth, so infer the prefix from a known page instead of re-reading env.
    idx = (DIST / "index.html").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'href="(/[^"]*/)?rss\.xml"', idx)
    if m and m.group(1):
        base = m.group(1)
    m2 = re.search(r'<link rel="canonical" href="https?://[^/]+(/[^"]*)"', idx)
    if m2 and m2.group(1) not in ("/", ""):
        base = m2.group(1)

    checked, link_problems = internal_links(base)
    cite_count, cite_problems = citations()
    meta_problems = feed_and_meta(base)
    problems = link_problems + cite_problems + meta_problems

    report = {
        "base_path": base,
        "internal_links_checked": checked,
        "citations_checked": cite_count,
        "pages": len(list(DIST.rglob("*.html"))),
        "problems": problems,
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
