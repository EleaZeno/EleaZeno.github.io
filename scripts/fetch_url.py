#!/usr/bin/env python3
"""Minimal URL fetcher for cron runs (web_extract is unavailable, execute_code blocked).

Usage:
  python3 scripts/fetch_url.py <url> [--chars N] [--raw]
"""
import argparse
import gzip
import io
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return raw.decode("utf-8", "replace")


def strip(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|section|article)>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&mdash;", "-"), ("&ndash;", "-"),
                 ("&rsquo;", "'"), ("&lsquo;", "'"), ("&ldquo;", '"'), ("&rdquo;", '"')):
        text = text.replace(a, b)
    text = re.sub(r"&#x?[0-9a-fA-F]+;", " ", text)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--chars", type=int, default=9000)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--out", help="write full text here instead of truncating to stdout")
    a = ap.parse_args()
    try:
        body = fetch(a.url)
    except Exception as e:
        print(f"FETCH_FAIL {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
    out = body if a.raw else strip(body)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"chars={len(out)} -> {a.out}")
    else:
        print(out[:a.chars])
        if len(out) > a.chars:
            print(f"\n[... {len(out) - a.chars} more chars omitted ...]")
    print("FETCH_EXIT=0", file=sys.stderr)


if __name__ == "__main__":
    main()
