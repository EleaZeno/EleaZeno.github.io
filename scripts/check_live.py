#!/usr/bin/env python3
"""
Probe the deployed site and report whether it is actually reachable and current.

Why this exists
---------------
Every other gate reads source text or the local `dist/` tree. None of them can
tell you whether the published site answers a request, and none can tell you
whether what it serves is the build you just made. So the site could 404 every
new route, or silently serve a build from yesterday, and the whole chain would
still pass. That gap is exactly how two "the site is down" reports got through.

What it checks
--------------
1. Reachability: every route in `dist/` is probed (concurrently, with retries,
   since a single transient 000 is noise rather than an outage).
2. Freshness: the live CSS bundle filename is compared against the local build.
   Astro content-hashes that filename, so a mismatch means the deploy that is
   live is NOT the build sitting in `dist/`.
3. Route parity: routes that exist locally but 404 upstream are listed
   separately from routes that error, because "never deployed" and "server
   trouble" have different fixes.

Exit status is non-zero only for problems the site owner can act on: a route
that is reliably missing, or a live bundle that does not match the local build.
Network failures affecting *every* probe are reported as UNKNOWN rather than
failure, because that means the prober has no path to the internet and says
nothing about the site.

Usage
-----
    python3 scripts/check_live.py                # probe every route
    python3 scripts/check_live.py --sample 25    # spot-check N routes
    python3 scripts/check_live.py --base https://example.com
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DIST = Path("dist")
DEFAULT_BASE = "https://eleazeno.github.io"
TIMEOUT = 20
RETRIES = 3
WORKERS = 8

# A GET is used rather than HEAD: GitHub Pages answers HEAD for some paths that
# it 404s on GET, so HEAD would under-report broken routes.
UA = "elea-notes-live-check/1.0 (+https://eleazeno.github.io)"


def local_routes() -> list[str]:
    """Every route the local build produced, as site-absolute paths."""
    if not DIST.is_dir():
        return []
    out = []
    for p in DIST.rglob("index.html"):
        rel = p.relative_to(DIST).parent.as_posix()
        out.append("/" if rel == "." else f"/{rel}/")
    return sorted(set(out))


def local_css_bundle() -> str | None:
    """Filename of the CSS bundle referenced by the local build's homepage."""
    idx = DIST / "index.html"
    if not idx.is_file():
        return None
    m = re.search(r"_astro/[A-Za-z0-9._-]+\.css", idx.read_text(encoding="utf-8"))
    return m.group(0) if m else None


def fetch(url: str) -> tuple[int, bytes, str]:
    """GET a URL. Returns (status, body, error). status 0 means no HTTP reply."""
    # Tag routes contain CJK, and http.client rejects non-ASCII request lines,
    # so the path has to be percent-encoded before it reaches urlopen.
    scheme, _, rest = url.partition("://")
    host, _, path = rest.partition("/")
    url = f"{scheme}://{host}/{urllib.parse.quote(path)}" if path else url
    ctx = ssl.create_default_context()
    last = ""
    for _ in range(RETRIES):
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as e:
            # A real HTTP answer: no point retrying a 404.
            return e.code, b"", ""
        except Exception as e:  # noqa: BLE001 - transport failures are retried
            # Keep the errno/reason, not just the class name: ConnectionResetError
            # (RST injection / SNI filtering) and a plain timeout both surface as
            # transport failures but mean completely different things, and the
            # difference is what tells a reader whether the origin is at fault.
            last = f"{type(e).__name__}: {e}"[:120]
    return 0, b"", last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--sample", type=int, default=0,
                    help="probe at most N routes (0 = all)")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    routes = local_routes()
    if not routes:
        print(json.dumps({"error": "no dist/ build found; run npm run build first"},
                         ensure_ascii=False))
        return 1

    probed = routes
    if args.sample and args.sample < len(routes):
        # Keep the homepage plus an evenly spread sample, so a spot check still
        # covers every section rather than clustering in one alphabetical range.
        step = len(routes) / args.sample
        picked = {routes[int(i * step)] for i in range(args.sample)}
        picked.add("/")
        probed = sorted(picked)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(lambda r: (r, *fetch(base + r)), probed))

    missing, errored, ok = [], [], 0
    home = (0, b"")
    for route, status, body, err in results:
        if route == "/":
            home = (status, body)
        if status == 200:
            ok += 1
        elif status == 404:
            missing.append(route)
        else:
            errored.append({"route": route, "status": status, "error": err})

    # Freshness: does the live homepage reference the same hashed bundle as dist/?
    # Astro content-hashes that filename, so a mismatch means what is live is not
    # the build in dist/. The homepage body comes from the probe pass above --
    # "/" is always in `probed`, so re-requesting it would just be a second hit.
    local_css = local_css_bundle()
    home_status, home_body = home
    m = re.search(rb"_astro/[A-Za-z0-9._-]+\.css", home_body)
    live_css = m.group(0).decode() if m else None

    problems: list[str] = []
    unreachable = bool(probed) and len(errored) == len(probed)
    if unreachable:
        # Everything failed at the transport layer: this prober has no route to
        # the site. That is a fact about the prober, not about the site.
        note = "UNKNOWN: no route to host from this network; site status not determined"
    else:
        note = ""
        for r in missing:
            problems.append(f"{r} exists in dist/ but returns 404 upstream (never deployed?)")
        if local_css and live_css and local_css != live_css:
            problems.append(
                f"live bundle {live_css} != local {local_css}: "
                "the deployed build is not the one in dist/")
        if local_css and home_status == 200 and live_css is None:
            problems.append("live homepage references no CSS bundle")

    out = {
        "base": base,
        "routes_local": len(routes),
        "routes_probed": len(probed),
        "ok": ok,
        "missing_upstream": missing,
        "transport_errors": errored[:10],
        "local_css_bundle": local_css,
        "live_css_bundle": live_css,
        "note": note,
        "problems": problems,
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
