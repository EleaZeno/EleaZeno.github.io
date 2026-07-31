#!/usr/bin/env python3
"""Build-time gate: jargon the prose leans on that has no concept page.

Why this exists
---------------
`check_wiki.py` already reports `uncovered_terms`, but only for the hand-curated
`WATCH_TERMS` tuple -- it can only find gaps somebody already thought of. The
failure this script catches is the one nobody notices: an article introduces a
term in bold, or declares it under `prerequisites:`, or drops it in a
`<Prereq>` block, and no page on the site ever defines it. The reader hits a
list of words and is stuck.

Three signals, all authored on purpose (so they are high-precision, unlike a
generic noun-phrase extractor over Chinese prose):

  1. `prerequisites:` in frontmatter that resolves to no concept slug
     -- fatal. Declaring a floor you never built is a broken promise, and
     `<Prereq>` renders it as a link.
  2. `<Prereq>` / `<Check>` component bodies naming a term with no page
     -- fatal for Prereq (it renders as a reading floor), advisory for Check.
  3. **Bolded** technical terms in classics/posts prose that match no concept
     title or alias -- advisory. Bold is how this site marks "this is the name
     of a thing", so a bolded term with no page is a candidate gap, but bold is
     also used for emphasis, so this cannot be fatal.

Usage
-----
    python3 scripts/check_terms.py            # all collections
    python3 scripts/check_terms.py --strict   # advisory findings become fatal
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

CONCEPTS = "src/content/concepts/"
ARTICLE_DIRS = ("src/content/posts/", "src/content/classics/", "src/content/dreams/")

# Bold spans that are never concept candidates: pure numbers, punctuation-only,
# single latin letters, and the site's own rhetorical furniture.
NOT_A_TERM = re.compile(
    r"^(?:[\d\s.,%×·—\-+()（）:：]+|[A-Za-z]|"
    r"注|按|即|但|而|所以|因此|也就是说|换句话说|重点|结论|问题|答案|是|不是|对|错)$"
)

# A <Prereq> item longer than this is a sentence, not the name of a thing.
MAX_TERM_LEN = 24


def watchlist() -> tuple[str, ...]:
    """The curated term watchlist, imported from check_wiki rather than copied.

    One list, one place to add a term. Falls back to empty (advisory signal 3
    simply goes quiet) if check_wiki is unavailable, so this gate never fails
    the build over its own plumbing.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import check_wiki  # type: ignore

        return tuple(check_wiki.WATCH_TERMS)
    except Exception:
        return ()


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse just enough YAML for our own frontmatter shapes."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    head, body = text[3:end], text[end + 3 :]
    data: dict = {}
    key = None
    for line in head.splitlines():
        m = re.match(r"([A-Za-z_]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            data[key] = val
            if val.startswith("[") and val.endswith("]"):
                data[key + "_inline"] = [
                    x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()
                ]
        elif line.strip().startswith("- ") and key:
            data.setdefault(key + "_list", []).append(line.strip()[2:].strip().strip("\"'"))
    return data, body


def prose_only(body: str) -> str:
    """Drop anything that is not our own running prose.

    Quoted primary sources are the author's words, not ours to gloss; code and
    math are not prose at all.
    """
    body = re.sub(r"```[\s\S]*?```", "", body)
    body = re.sub(r"(?m)^>.*$", "", body)
    body = re.sub(r"`[^`]*`", "", body)
    body = re.sub(r"\$\$[\s\S]*?\$\$", "", body)
    return body


def load_concepts() -> tuple[set[str], dict[str, dict]]:
    """Return (every surface form that resolves, slug -> frontmatter)."""
    covered: set[str] = set()
    by_slug: dict[str, dict] = {}
    # .mdx included: concepts carrying <Sidenote> must be MDX (see content.config.ts).
    for path in sorted(glob.glob(CONCEPTS + "*.md") + glob.glob(CONCEPTS + "*.mdx")):
        slug = os.path.splitext(os.path.basename(path))[0]
        data, _ = split_frontmatter(open(path, encoding="utf-8").read())
        by_slug[slug] = data
        covered.add(slug)
        title = data.get("title", "").strip().strip("\"'")
        if title:
            covered.add(title)
        for alias in data.get("aliases_inline", []) + data.get("aliases_list", []):
            if alias:
                covered.add(alias)
    return covered, by_slug


def resolves(term: str, covered: set[str]) -> bool:
    """Does this surface form reach a concept page?

    Matching is containment in both directions: '区块头' should count as covered
    by a page titled '区块头（block header）', and a page titled '区块' should
    not be silently credited for '区块头'. Longest-first containment is what the
    autolinker does at build time, so mirroring it here keeps the gate honest.
    """
    t = term.strip().strip("*_ ").lower()
    if not t:
        return True
    for c in covered:
        cl = c.strip().lower()
        if not cl:
            continue
        if t == cl or t in cl:
            return True
    return False


def main() -> int:
    strict = "--strict" in sys.argv
    covered, concepts = load_concepts()

    fatal: dict[str, list[str]] = {}
    advisory: dict[str, list[str]] = {}

    def add(bucket: dict[str, list[str]], path: str, msg: str) -> None:
        bucket.setdefault(path, []).append(msg)

    # ---- signal 1 + 2: declared floors must exist -----------------------
    articles: dict[str, str] = {}
    for d in ARTICLE_DIRS:
        for path in sorted(glob.glob(d + "*.md")) + sorted(glob.glob(d + "*.mdx")):
            articles[path] = open(path, encoding="utf-8").read()

    for path, text in articles.items():
        data, body = split_frontmatter(text)

        declared = data.get("prerequisites_inline", []) + data.get("prerequisites_list", [])
        for slug in declared:
            if slug and slug not in concepts:
                add(fatal, path, f"prerequisites: '{slug}' has no concept page")

        # <Prereq ids={[...]}/> and <Prereq>term, term</Prereq>
        for m in re.finditer(r"<Prereq\b([^>]*)>([\s\S]*?)</Prereq>", body):
            attrs, inner = m.group(1), m.group(2)
            for slug in re.findall(r"['\"]([a-z0-9-]+)['\"]", attrs):
                if slug not in concepts:
                    add(fatal, path, f"<Prereq> references missing concept '{slug}'")
            for term in re.split(r"[、,，/]\s*", re.sub(r"<[^>]+>", "", inner)):
                term = term.strip()
                if term and len(term) <= MAX_TERM_LEN and not resolves(term, covered):
                    add(fatal, path, f"<Prereq> names undefined term '{term}'")

        for m in re.finditer(r"<Prereq\b([^>]*?)/>", body):
            for slug in re.findall(r"['\"]([a-z0-9-]+)['\"]", m.group(1)):
                if slug not in concepts:
                    add(fatal, path, f"<Prereq> references missing concept '{slug}'")

        # ---- signal 3: WATCH_TERMS leaned on but never defined ----------
        #
        # Bold was tried here and abandoned: on this site bold marks emphasis
        # ('**数字是真的**'), not the name of a thing, so it produced ~113
        # findings of which zero were real. The reliable signal is the curated
        # watchlist in check_wiki.py -- reused rather than duplicated -- scoped
        # to terms the article actually leans on (3+ mentions), which is the
        # threshold where a reader who doesn't know it gets stuck.
        text_prose = prose_only(body)
        for term in watchlist():
            n = text_prose.count(term)
            if n >= 3 and not resolves(term, covered):
                add(advisory, path, f"leans on '{term}' ({n}x) with no page")

    out = {
        "concepts": len(concepts),
        "articles": len(articles),
        "fatal": fatal,
        "advisory": advisory,
        "fatal_count": sum(len(v) for v in fatal.values()),
        "advisory_count": sum(len(v) for v in advisory.values()),
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()

    if fatal:
        return 1
    if strict and advisory:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
