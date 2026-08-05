#!/usr/bin/env python3
"""Fetch a URL and dump full visible text to a file (no truncation).

Usage: python3 scripts/fetch_full.py <url> <outfile>

Exists because scripts/fetch_url.py caps its stdout, which loses the body of
long arXiv HTML papers, and web_extract is search-only on this host.
"""
import html
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def visible_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<!--.*?-->", " ", raw)
    raw = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section|blockquote)>", "\n", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\u00a0]+", " ", raw)
    raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
    return "\n".join(line.strip() for line in raw.splitlines())


def main() -> int:
    url, out = sys.argv[1], sys.argv[2]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read()
        status = resp.status
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    result = visible_text(text)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(result)
    print(f"RUN_EXIT=0 status={status} bytes={len(body)} chars={len(result)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
