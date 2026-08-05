#!/usr/bin/env python3
"""Build-time gate: tag vocabulary drift that silently splits one topic in two.

Why this exists
---------------
Every other gate in this repo reads prose. None of them reads `tags:`, because
tags render as small grey text and a wrong one never looks broken. But tags are
not decoration: `reader_model.py brief` aggregates `post_tags` into the
`top_tags` ranking I read every morning to decide what to write next.

The failure this catches happened for real. On 2026-08-04 I tagged two posts
`agents`; four earlier posts said `agent`. Both spellings are reasonable and
both built fine. The brief then reported `llm` (6) as the top topic, with
`agent` (4) and `agents` (3) as separate rows below it -- when the true count
was 7, the largest cluster on the site. The number I steer by was wrong, and
nothing was red. Same shape as the reader-model gap: my own input quietly
degraded while every check passed.

Two assertions, both cheap:

  1. No two tags in use may normalize to the same key -- fatal. Normalization
     folds case and the English plural `s`/`es`. `agent` vs `agents` is one
     topic wearing two names; picking either is fine, using both is not.
  2. A tag used exactly once that is an edit-distance-1 neighbour of a
     frequent tag is a likely typo -- advisory, because genuinely new topics
     also start life with a count of one.

Usage
-----
    python3 scripts/check_tags.py            # all posts
    python3 scripts/check_tags.py --strict   # advisory findings become fatal
"""

from __future__ import annotations

import glob
import json
import re
import sys

POST_DIRS = ("src/content/posts/", "src/content/classics/")

# Tags that legitimately end in `s` as part of the word, not as a plural.
# Folding these would invent a collision rather than find one.
NEVER_DEPLURALIZE = {"physics", "mathematics", "genomics", "economics", "ops", "systems"}


def read_tags(path: str) -> list[str]:
    """Pull the inline `tags: [...]` list out of frontmatter.

    Deliberately not a YAML parse: the repo's other gates hand-roll this for
    the same reason (no dependency), and every post in this collection uses
    the inline-list form.
    """
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    head = text[3:end] if end != -1 else text[3:]
    m = re.search(r"(?m)^tags:\s*\[(.*?)\]\s*$", head)
    if not m:
        return []
    return [t.strip().strip("\"'") for t in m.group(1).split(",") if t.strip()]


def normalize(tag: str) -> str:
    """Fold the differences that are spelling, not meaning."""
    key = tag.strip().lower().replace("_", "-")
    if key in NEVER_DEPLURALIZE:
        return key
    if key.endswith("es") and len(key) > 4:
        return key[:-2]
    if key.endswith("s") and not key.endswith("ss") and len(key) > 3:
        return key[:-1]
    return key


def edit_distance_1(a: str, b: str) -> bool:
    """True when a and b differ by exactly one insert, delete, or substitution."""
    if a == b:
        return False
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long)):
        if long[:i] + long[i + 1 :] == short:
            return True
    return False


def main() -> int:
    strict = "--strict" in sys.argv

    paths: list[str] = []
    for d in POST_DIRS:
        paths += sorted(glob.glob(d + "*.md") + glob.glob(d + "*.mdx"))

    # tag -> {count, paths}; and normalized key -> set of raw spellings.
    counts: dict[str, int] = {}
    where: dict[str, list[str]] = {}
    groups: dict[str, set[str]] = {}
    for path in paths:
        for tag in read_tags(path):
            counts[tag] = counts.get(tag, 0) + 1
            where.setdefault(tag, []).append(path.split("/")[-1])
            groups.setdefault(normalize(tag), set()).add(tag)

    fatal: list[dict] = []
    for key, spellings in sorted(groups.items()):
        if len(spellings) < 2:
            continue
        variants = sorted(spellings, key=lambda t: (-counts[t], t))
        fatal.append(
            {
                "normalized": key,
                "spellings": {t: counts[t] for t in variants},
                "combined": sum(counts[t] for t in variants),
                "keep": variants[0],
                "files": {t: where[t] for t in variants[1:]},
            }
        )

    frequent = {t for t, n in counts.items() if n >= 3}
    advisory: list[dict] = []
    for tag, n in sorted(counts.items()):
        if n != 1:
            continue
        near = sorted(f for f in frequent if edit_distance_1(tag.lower(), f.lower()))
        if near:
            advisory.append({"tag": tag, "in": where[tag], "near": near})

    out = {
        "posts": len(paths),
        "distinct_tags": len(counts),
        "top": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]),
        "collisions": fatal,
        "possible_typos": advisory,
        "fatal_count": len(fatal),
        "advisory_count": len(advisory),
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()

    if fatal:
        print(
            "\ntag collision: one topic is split across spellings, so "
            "`reader_model.py brief` will rank it below its true size.",
            file=sys.stderr,
        )
        return 1
    if strict and advisory:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
