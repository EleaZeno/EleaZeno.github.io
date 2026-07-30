#!/usr/bin/env python3
"""Scan a wide set of frontier sources and rank what is worth reading today.

Design intent
-------------
The failure mode this fixes: writing about whatever a single arXiv listing
happened to surface, which yields competent-but-narrow engineering posts.
Breadth first, then depth. Three tiers:

  primary    labs, journals, standards bodies, preprint servers. Authoritative;
             cite these.
  analysis   independent technical analysis worth reading, still not primary.
  chatter    aggregators and Chinese tech media. These are LEADS ONLY — they
             tell you what people are excited about, and they are frequently
             wrong or exaggerated. Never cite chatter; use it to find the
             primary source and check whether the claim survives.

Usage
-----
    python3 scripts/scan_frontier.py                  # ranked digest
    python3 scripts/scan_frontier.py --tier primary   # one tier
    python3 scripts/scan_frontier.py --hours 48       # widen the window
    python3 scripts/scan_frontier.py --json           # machine-readable
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# tier: primary | analysis | chatter
# domain: ai | crypto | systems | science | bio | space | theory
SOURCES: list[dict] = [
    # ---- primary: labs & standards ----
    {"key": "openai", "url": "https://openai.com/news/rss.xml", "tier": "primary", "domain": "ai", "label": "OpenAI"},
    {"key": "arxiv-ai", "url": "http://export.arxiv.org/rss/cs.AI", "tier": "primary", "domain": "ai", "label": "arXiv cs.AI"},
    {"key": "arxiv-lg", "url": "http://export.arxiv.org/rss/cs.LG", "tier": "primary", "domain": "ai", "label": "arXiv cs.LG"},
    {"key": "arxiv-cl", "url": "http://export.arxiv.org/rss/cs.CL", "tier": "primary", "domain": "ai", "label": "arXiv cs.CL"},
    {"key": "arxiv-quant", "url": "http://export.arxiv.org/rss/quant-ph", "tier": "primary", "domain": "theory", "label": "arXiv quant-ph"},
    {"key": "mit-ai", "url": "https://news.mit.edu/rss/topic/artificial-intelligence2", "tier": "primary", "domain": "ai", "label": "MIT News"},
    {"key": "ethresearch", "url": "https://ethresear.ch/latest.rss", "tier": "primary", "domain": "crypto", "label": "Ethereum Research"},
    # ---- primary: journals & science ----
    {"key": "nature", "url": "https://www.nature.com/nature.rss", "tier": "primary", "domain": "science", "label": "Nature"},
    {"key": "science", "url": "https://www.science.org/rss/news_current.xml", "tier": "primary", "domain": "science", "label": "Science"},
    {"key": "nejm", "url": "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm", "tier": "primary", "domain": "bio", "label": "NEJM"},
    {"key": "biorxiv", "url": "http://connect.biorxiv.org/biorxiv_xml.php?subject=all", "tier": "primary", "domain": "bio", "label": "bioRxiv"},
    {"key": "nasa", "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss", "tier": "primary", "domain": "space", "label": "NASA"},
    {"key": "phys", "url": "https://phys.org/rss-feed/", "tier": "primary", "domain": "science", "label": "Phys.org"},
    # ---- analysis ----
    {"key": "quanta", "url": "https://www.quantamagazine.org/feed/", "tier": "analysis", "domain": "science", "label": "Quanta"},
    {"key": "semianalysis", "url": "https://semianalysis.com/feed/", "tier": "analysis", "domain": "systems", "label": "SemiAnalysis"},
    # ---- chatter: leads only, never cite ----
    {"key": "hn", "url": "https://hnrss.org/frontpage?points=250", "tier": "chatter", "domain": "systems", "label": "Hacker News"},
    {"key": "qbitai", "url": "https://www.qbitai.com/feed", "tier": "chatter", "domain": "ai", "label": "量子位"},
    {"key": "solidot", "url": "https://www.solidot.org/index.rss", "tier": "chatter", "domain": "systems", "label": "Solidot"},
    {"key": "36kr", "url": "https://36kr.com/feed", "tier": "chatter", "domain": "systems", "label": "36氪"},
    {"key": "infoq-cn", "url": "https://www.infoq.cn/feed", "tier": "chatter", "domain": "systems", "label": "InfoQ 中国"},
    {"key": "ifanr", "url": "https://www.ifanr.com/feed", "tier": "chatter", "domain": "systems", "label": "爱范儿"},
]

# Words that mark a genuine step change rather than an incremental tweak.
BREAKTHROUGH = [
    "breakthrough", "first time", "unprecedented", "record", "solves",
    "proof", "proves", "discovery", "discovered", "milestone", "beats",
    "outperforms", "state-of-the-art", "sota", "emergent", "surpasses",
    "new class", "novel mechanism", "首次", "突破", "首个", "证明", "发现",
]

# Words that mark narrow incremental engineering. Not disqualifying, but this
# is exactly the "just an optimisation paper" failure mode, so it costs points.
RETRACTION = (
    "withdrawn", "retracted", "do not rely on",
    "should not rely on or cite", "substantial theoretical errors",
)

INCREMENTAL = [
    "we propose a", "slight", "marginal", "fine-tuning recipe", "ablation",
    "benchmark suite", "survey", "position paper", "toolkit", "we present a framework",
]

# Cross-disciplinary or high-consequence topics get a boost: the brief asks for
# multi-disciplinary frontier work, not one narrow lane.
FRONTIER = [
    "quantum", "nuclear fusion", "superconduct", "room temperature", "gene editing",
    "crispr", "protein", "neural interface", "brain-computer", "agi",
    "self-improving", "interpretability", "mechanistic", "alignment",
    "formal verification", "zero-knowledge", "homomorphic", "photonic",
    "neuromorphic", "biocomputing", "organoid", "de novo", "world model",
    "continual learning", "reasoning", "robotics", "materials discovery",
]


@dataclass
class Item:
    title: str
    url: str
    source: str
    tier: str
    domain: str
    published: str | None
    summary: str
    score: float = 0.0
    retracted: bool = False
    signals: list[str] = field(default_factory=list)


def fetch(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", unescape(s)).strip()


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.replace("Z", "+0000"), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def parse_feed(raw: bytes, src: dict) -> list[Item]:
    """Handle RSS 2.0, RDF (Nature/Science/bioRxiv) and Atom in one pass."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }
    out: list[Item] = []

    nodes = root.findall(".//item") or root.findall(".//atom:entry", ns)
    for n in nodes:
        title = n.findtext("title") or n.findtext("atom:title", default="", namespaces=ns) or ""
        link = n.findtext("link") or ""
        if not link:
            le = n.find("atom:link", ns)
            if le is not None:
                link = le.get("href", "")
        desc = (
            n.findtext("description")
            or n.findtext("atom:summary", default="", namespaces=ns)
            or n.findtext("{http://purl.org/rss/1.0/}description")
            or ""
        )
        date_raw = (
            n.findtext("pubDate")
            or n.findtext("dc:date", default="", namespaces=ns)
            or n.findtext("atom:updated", default="", namespaces=ns)
            or n.findtext("{http://purl.org/dc/elements/1.1/}date")
        )
        title = strip_html(title)
        if not title:
            continue
        dt = parse_date(date_raw)
        out.append(
            Item(
                title=title,
                url=link.strip(),
                source=src["label"],
                tier=src["tier"],
                domain=src["domain"],
                published=dt.isoformat() if dt else None,
                summary=strip_html(desc)[:600],
            )
        )
    return out


def score(item: Item, now: datetime) -> Item:
    text = f"{item.title} {item.summary}".lower()
    s = 0.0
    sig: list[str] = []

    # Tier weighting: primary sources are what we can actually cite.
    s += {"primary": 2.0, "analysis": 1.2, "chatter": 0.4}.get(item.tier, 0.5)

    hits = [w for w in BREAKTHROUGH if w in text]
    if hits:
        s += min(len(hits), 3) * 1.1
        sig.append(f"breakthrough:{','.join(hits[:3])}")

    fr = [w for w in FRONTIER if w in text]
    if fr:
        s += min(len(fr), 3) * 0.9
        sig.append(f"frontier:{','.join(fr[:3])}")

    # Retraction guard. A withdrawn or retracted item must never surface as a
    # lead: arXiv keeps the abstract page live and the title still reads like a
    # breakthrough, so keyword scoring alone would happily rank it top.
    if any(r in text for r in RETRACTION):
        item.retracted = True
        s -= 100.0
        sig.append('RETRACTED')

    inc = [w for w in INCREMENTAL if w in text]
    if inc:
        s -= len(inc) * 0.8
        sig.append(f"incremental:{','.join(inc[:2])}")

    # Freshness: today is worth more than last week.
    if item.published:
        try:
            age_h = (now - datetime.fromisoformat(item.published)).total_seconds() / 3600
            if age_h < 24:
                s += 1.0
            elif age_h < 48:
                s += 0.5
        except Exception:
            pass

    # Substance heuristic: a one-line teaser is usually PR.
    if len(item.summary) > 300:
        s += 0.4

    item.score = round(s, 2)
    item.signals = sig
    return item


def collect(hours: int, tier: str | None) -> list[Item]:
    srcs = [s for s in SOURCES if not tier or s["tier"] == tier]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    items: list[Item] = []
    errors: list[str] = []

    def one(src: dict) -> tuple[list[Item], str | None]:
        try:
            return parse_feed(fetch(src["url"]), src), None
        except Exception as exc:
            return [], f"{src['key']}: {type(exc).__name__}"

    with futures.ThreadPoolExecutor(max_workers=10) as ex:
        for got, err in ex.map(one, srcs):
            items.extend(got)
            if err:
                errors.append(err)

    fresh = []
    for it in items:
        if it.published:
            try:
                if datetime.fromisoformat(it.published) < cutoff:
                    continue
            except Exception:
                pass
        fresh.append(score(it, now))

    # Dedupe by normalised title: the same story shows up across many feeds.
    seen: dict[str, Item] = {}
    for it in sorted(fresh, key=lambda x: -x.score):
        key = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", it.title.lower())[:60]
        if key and key not in seen:
            seen[key] = it

    ordered = sorted(seen.values(), key=lambda x: -x.score)

    # Cap any single source so one prolific feed (arXiv posts ~100/day)
    # cannot crowd out the rest of the world.
    per_source: dict[str, int] = {}
    ranked = []
    for it in ordered:
        n = per_source.get(it.source, 0)
        if n >= 4:
            continue
        per_source[it.source] = n + 1
        ranked.append(it)
    if errors:
        print(f"[scan] {len(errors)} source(s) failed: {'; '.join(errors)}", file=sys.stderr)
    return ranked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--tier", choices=["primary", "analysis", "chatter"])
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ranked = collect(args.hours, args.tier)[: args.limit]

    if args.json:
        print(json.dumps([asdict(i) for i in ranked], ensure_ascii=False, indent=2))
        return 0

    by_tier: dict[str, list[Item]] = {}
    for it in ranked:
        by_tier.setdefault(it.tier, []).append(it)

    for tier in ("primary", "analysis", "chatter"):
        got = by_tier.get(tier, [])
        if not got:
            continue
        note = " (leads only — trace to primary before citing)" if tier == "chatter" else ""
        print(f"\n=== {tier.upper()}{note} ===")
        for it in got:
            print(f"[{it.score:>5}] {it.source} · {it.domain}")
            print(f"        {it.title[:110]}")
            print(f"        {it.url}")
            if it.signals:
                print(f"        signals: {' | '.join(it.signals)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
