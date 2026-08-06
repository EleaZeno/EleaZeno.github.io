#!/usr/bin/env python3
"""Network gate: does the arXiv source I cited still say what I claim it says?

Why this exists
---------------
`check_quotes.py` has no `http` in it. It verifies that a quoted line exists in
the local article text -- nothing more. So the entire class of "the source moved
and my citation didn't" is invisible to every gate in this repo.

It bit twice in two days, both found by hand during the nightly reflection:

  * 2026-08-04, TokTier: I cited `2607.29678v1` with the v1 title. v2 had gone
    up on 08-03, a day *before* I published, and the title changed
    (`Exact Stateful` -> `Exact Stateful CPU+GPU`). Nothing was red.
  * 2026-08-05 dream: reasoning about which words v1 vs v2 added, I asserted a
    title difference that did not exist, because I never diffed them.

Both are the same mechanical gap: the citation is a claim about a remote object,
and no check ever asked the remote object.

What it asserts, per arXiv source in frontmatter
------------------------------------------------
1. The id resolves at all -- a citation to a nonexistent id is fatal.
2. The cited title matches the title of the version I claim, compared on a
   loose skeleton (case, punctuation and whitespace folded) so that a real
   wording change trips it but a typographic one does not. Fatal: this is the
   one that misleads a reader who trusts the citation.
3. If I pinned `vN` in `outlet:` and a later version exists, that is advisory,
   not fatal. Papers get revised after publication and back-dating my own post
   is not always right; but I want to be told, because a revision that lands
   *before* my pubDate (as TokTier's did) means I cited a stale version I could
   have read.

Not in the default `gate` chain: it needs the network, and per AGENTS.md an
offline run must not redden a chain that has nothing to do with code. It rides
with `gate:live`. Total network failure reports UNKNOWN rather than failure,
for the same reason `check_live.py` does.

Usage
-----
    python3 scripts/check_sources.py
    python3 scripts/check_sources.py --strict   # advisory becomes fatal
    python3 scripts/check_sources.py --file src/content/posts/x.md
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import urllib.error
import urllib.request

API = "https://export.arxiv.org/api/query?id_list="
# concepts/ is here because it was missing for two days and that was invisible:
# 34 of 73 concept files carry `sources:`, 10 of them arXiv links, and this gate
# scanned none of them. Verified 2026-08-07 by planting a fabricated title in
# concepts/kv-cache.md -- every gate in the chain passed it. The evergreen
# entries are exactly the pages a reader arrives at from a search engine and
# trusts most, so an unchecked citation there outlives an unchecked one in a
# dated post.
POST_DIRS = ("src/content/posts/", "src/content/classics/", "src/content/concepts/")
TIMEOUT = 30

ARXIV_ID = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(v\d+)?", re.I)
VERSION_IN_OUTLET = re.compile(r"(\d{4}\.\d{4,5})(v\d+)", re.I)


def skeleton(s: str) -> str:
    """Fold everything that is typography, keep everything that is wording.

    A trailing `(arXiv:2607.14567v2)` is a citation-format choice this repo
    sometimes makes, not a claim about wording, so it is stripped before
    comparing. Everything else survives: the point of this gate is to catch a
    title I paraphrased or invented.
    """
    s = re.sub(r"\(\s*arxiv:\s*\d{4}\.\d{4,5}(v\d+)?\s*\)\s*$", "", s.strip(), flags=re.I)
    s = s.lower()
    s = re.sub(r"[\s\u00a0]+", " ", s)
    s = re.sub(r"[^a-z0-9+ ]+", "", s)
    return s.strip()


def sources_of(path: str) -> list[dict]:
    """Extract frontmatter `sources:` entries (title/url/outlet triples).

    Hand-rolled like the other gates: no YAML dependency, and the shape is
    fixed by this repo's own template.
    """
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    head = text[3:end] if end != -1 else text[3:]
    m = re.search(r"(?ms)^sources:\s*\n(.*?)(?=^\S|\Z)", head)
    if not m:
        return []
    out: list[dict] = []
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append({})
            stripped = stripped[2:].strip()
        if not out:
            continue
        kv = re.match(r"(title|url|outlet):\s*(.*)$", stripped)
        if kv:
            out[-1][kv.group(1)] = kv.group(2).strip().strip("\"'")
    return out


def fetch(arxiv_id: str) -> dict | None:
    """Return {id,title} for an arXiv id, or None when the id does not resolve.

    Raises urllib errors so the caller can distinguish "no network" (every
    probe fails) from "this id is bad" (one probe returns no entry).
    """
    with urllib.request.urlopen(API + arxiv_id, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8", "replace")
    ids = re.findall(r"<id>(http://arxiv\.org/abs/[^<]+)</id>", body)
    titles = re.findall(r"<title>(.*?)</title>", body, re.S)
    if not ids or len(titles) < 2:
        return None  # feed-level <title> only == no entry matched
    return {
        "id": ids[-1].rsplit("/", 1)[-1],
        "title": " ".join(titles[-1].split()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="advisory findings become fatal")
    ap.add_argument("--file", help="check one article instead of all")
    args = ap.parse_args()

    if args.file:
        paths = [args.file]
    else:
        paths = []
        for d in POST_DIRS:
            paths += sorted(glob.glob(d + "*.md") + glob.glob(d + "*.mdx"))

    fatal: list[dict] = []
    advisory: list[dict] = []
    checked = 0
    net_errors = 0
    cache: dict[str, dict | None] = {}

    for path in paths:
        name = path.split("/")[-1]
        for src in sources_of(path):
            url = src.get("url", "")
            m = ARXIV_ID.search(url)
            if not m:
                continue  # only arXiv is machine-checkable here
            base = m.group(1)
            cited_title = src.get("title", "")
            outlet = src.get("outlet", "")

            # Which version does this post claim? outlet wins, then the URL.
            vm = VERSION_IN_OUTLET.search(outlet)
            cited_ver = (vm.group(2) if vm else (m.group(2) or "")).lower()

            for key in {base, base + cited_ver if cited_ver else base}:
                if key not in cache:
                    try:
                        cache[key] = fetch(key)
                    except (urllib.error.URLError, OSError, TimeoutError) as exc:
                        net_errors += 1
                        cache[key] = None
                        advisory.append({"file": name, "id": key, "probe_failed": str(exc)[:80]})
            checked += 1

            latest = cache.get(base)
            if latest is None:
                fatal.append({"file": name, "id": base, "problem": "id does not resolve"})
                continue

            # Compare the cited title against the version the post claims.
            pinned = cache.get(base + cited_ver) if cited_ver else latest
            target = pinned or latest
            if cited_title and skeleton(cited_title) != skeleton(target["title"]):
                fatal.append(
                    {
                        "file": name,
                        "id": target["id"],
                        "problem": "cited title does not match the source",
                        "cited": cited_title,
                        "actual": target["title"],
                    }
                )

            live_ver = latest["id"].split("v")[-1]
            if cited_ver and cited_ver.lstrip("v") != live_ver:
                advisory.append(
                    {
                        "file": name,
                        "id": base,
                        "problem": "a newer version exists than the one cited",
                        "cited": cited_ver,
                        "latest": "v" + live_ver,
                        "latest_title": latest["title"],
                    }
                )

    out = {
        "articles": len(paths),
        "arxiv_sources_checked": checked,
        "fatal": fatal,
        "advisory": advisory,
        "fatal_count": len(fatal),
        "advisory_count": len(advisory),
    }

    # No path to the network says nothing about the citations. Same policy as
    # check_live.py: UNKNOWN, not failure.
    if checked and net_errors >= checked:
        out["verdict"] = "UNKNOWN (no network path to arxiv.org)"
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    if fatal:
        return 1
    if args.strict and advisory:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
