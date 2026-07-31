#!/usr/bin/env python3
"""
Diagnose why the site will not open, layer by layer.

`check_live.py` answers "is it up from here". That is not the same question as
"why can the user not reach it", and the two diverged badly: the site returned
200 to every probe while the browser showed ERR_CONNECTION_RESET. A reset is
injected mid-connection, so every origin-side check stays green and the real
signal only shows up if you separate the layers.

Layers, in the order a browser walks them:

  1. DNS      -- does the name resolve, and to the expected GitHub Pages set?
  2. TCP      -- does :443 accept a connection at all?
  3. TLS      -- does the handshake finish, and does the cert cover this host?
  4. HTTP     -- does a request return a status?
  5. Content  -- is the body the current build, or a stale/blank one?

Each layer prints PASS/FAIL independently. The first FAIL is the answer. A
reset at layer 2 or 3 with layers 1 and 4-5 healthy from elsewhere means the
origin is fine and the path is filtered -- nothing in this repo can fix it,
which is worth stating plainly instead of re-running origin checks.

Usage:
    python3 scripts/diagnose_access.py
    python3 scripts/diagnose_access.py --host eleazeno.github.io
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

EXPECTED_PAGES_IPS = {
    "185.199.108.153", "185.199.109.153",
    "185.199.110.153", "185.199.111.153",
}


def layer_dns(host: str) -> dict:
    """Resolve the host and compare against the known GitHub Pages address set."""
    out: dict = {"layer": "1-DNS", "host": host}
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, detail=f"{type(e).__name__}: {e}")
        return out
    v4 = sorted({i[4][0] for i in infos if i[0] == socket.AF_INET})
    v6 = sorted({i[4][0] for i in infos if i[0] == socket.AF_INET6})
    out["ipv4"], out["ipv6"] = v4, v6
    if not v4 and not v6:
        out.update(ok=False, detail="resolved to nothing")
        return out
    # A poisoned answer usually points somewhere outside the published range.
    unexpected = [ip for ip in v4 if ip not in EXPECTED_PAGES_IPS]
    if v4 and unexpected:
        out.update(ok=False, detail=f"unexpected A records: {unexpected}")
        return out
    out.update(ok=True, detail=f"{len(v4)} A / {len(v6)} AAAA")
    return out


def layer_tcp(ip: str, port: int = 443) -> dict:
    """Open a bare socket. Distinguishes refusal, reset and timeout."""
    out: dict = {"layer": "2-TCP", "target": f"{ip}:{port}"}
    s = socket.socket(socket.AF_INET6 if ":" in ip else socket.AF_INET,
                      socket.SOCK_STREAM)
    s.settimeout(8)
    try:
        s.connect((ip, port))
        out.update(ok=True, detail="accepted")
    except ConnectionResetError as e:
        out.update(ok=False, detail=f"RESET during connect: {e}")
    except socket.timeout:
        out.update(ok=False, detail="timeout (silently dropped)")
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, detail=f"{type(e).__name__}: {e}")
    finally:
        s.close()
    return out


def layer_tls(host: str, ip: str) -> dict:
    """Handshake with SNI set. A reset here (TCP already open) is the classic
    SNI-filtering signature: the filter reads the ClientHello, sees the name,
    and injects RST."""
    out: dict = {"layer": "3-TLS", "target": f"{ip} sni={host}"}
    ctx = ssl.create_default_context()
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(10)
    try:
        raw.connect((ip, 443))
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, detail=f"TCP failed first: {type(e).__name__}")
        raw.close()
        return out
    try:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            cert = tls.getpeercert()
            names = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
            out.update(ok=True, detail=f"{tls.version()}; SAN covers {len(names)} names",
                       san_sample=names[:4])
    except ConnectionResetError as e:
        out.update(ok=False, detail=f"RESET after ClientHello (SNI filtered?): {e}")
    except ssl.SSLCertVerificationError as e:
        out.update(ok=False, detail=f"cert does not cover {host}: {e.verify_message}")
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, detail=f"{type(e).__name__}: {e}")
    finally:
        try:
            raw.close()
        except OSError:
            pass
    return out


def layer_http(url: str) -> dict:
    """One plain request. Any status counts as the layer working."""
    out: dict = {"layer": "4-HTTP", "url": url}
    req = urllib.request.Request(url, headers={"User-Agent": "diagnose/1.0",
                                               "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            out.update(ok=True, status=r.status, bytes=len(body),
                       detail=f"HTTP {r.status}, {len(body)}B")
            out["_body"] = body
    except urllib.error.HTTPError as e:
        # The server answering is not the same as the site existing. A 404 on the
        # homepage means Pages has nothing published for this name -- treat it as
        # a failure, or a wildcard-DNS typo reads as a healthy origin.
        fatal = e.code in (404, 410)
        out.update(ok=not fatal, status=e.code,
                   detail=f"HTTP {e.code}" + (" -- no site published here" if fatal
                                              else " (server answered)"))
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, detail=f"{type(e).__name__}: {e}")
    return out


def layer_content(body: bytes) -> dict:
    """Is the served page a real build, or blank / an error shell?"""
    out: dict = {"layer": "5-Content"}
    text = body.decode("utf-8", "replace")
    has_css = "_astro/" in text
    title = ""
    if "<title>" in text:
        title = text.split("<title>", 1)[1].split("</title>", 1)[0][:70]
    # A GitHub 404 page is served with 200 in some misconfigurations.
    looks_404 = "There isn&#39;t a GitHub Pages site here" in text or \
                "404" in title
    if not body:
        out.update(ok=False, detail="empty body")
    elif looks_404:
        out.update(ok=False, detail="GitHub 'no site here' placeholder")
    elif not has_css:
        out.update(ok=False, detail="no bundled asset reference; not an Astro build")
    else:
        out.update(ok=True, detail=f"title={title!r}")
    return out


def proxy_env() -> dict:
    """Report whether this process is behind a proxy. Without this note the
    results are easy to over-read: a proxied PASS says nothing about a direct
    path, which is exactly the mistake that sent an earlier diagnosis sideways."""
    import os
    keys = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY")
    active = {k: os.environ[k] for k in keys if os.environ.get(k)}
    return {"behind_proxy": bool(active), "vars": active}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="eleazeno.github.io")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    host = args.host

    report: dict = {"host": host, "proxy": proxy_env(), "layers": []}

    dns = layer_dns(host)
    report["layers"].append(dns)

    ips = (dns.get("ipv4") or [])[:2]
    for ip in ips:
        report["layers"].append(layer_tcp(ip))
        report["layers"].append(layer_tls(host, ip))
    # v6 is worth one probe: a host with AAAA but no v6 route stalls browsers.
    for ip6 in (dns.get("ipv6") or [])[:1]:
        report["layers"].append(layer_tcp(ip6))

    http = layer_http(f"https://{host}/")
    body = http.pop("_body", b"")
    report["layers"].append(http)
    if http.get("ok") and body:
        report["layers"].append(layer_content(body))

    def is_local_v6_artefact(l: dict) -> bool:
        return (l["layer"].startswith("2") and ":" in str(l.get("target", ""))
                and "Network is unreachable" in str(l.get("detail", "")))

    if any(is_local_v6_artefact(l) for l in report["layers"]):
        report["note_v6"] = ("this host has no IPv6 route, so the AAAA probe "
                             "cannot say anything about the site")
    # Skip that artefact when picking the verdict: it is about the prober.
    first_fail = next((l for l in report["layers"]
                       if not l.get("ok") and not is_local_v6_artefact(l)), None)
    report["verdict"] = (
        "all layers pass from this host" if first_fail is None
        else f"first failure at {first_fail['layer']}: {first_fail['detail']}"
    )

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        pxy = report["proxy"]
        print(f"host: {host}")
        print(f"proxy: {'YES ' + str(list(pxy['vars'].values())[:1]) if pxy['behind_proxy'] else 'no (direct)'}")
        print()
        for l in report["layers"]:
            mark = "PASS" if l.get("ok") else "FAIL"
            tgt = l.get("target") or l.get("url") or l.get("host") or ""
            print(f"  [{mark}] {l['layer']:<10} {tgt:<34} {l['detail']}")
        print()
        print("verdict:", report["verdict"])
        if first_fail is None:
            print("note: reachable from here. If a browser still shows"
                  " ERR_CONNECTION_RESET, the reset is injected on that client's"
                  " path -- no change in this repo can fix it.")
    # Exit non-zero only when the origin itself looks broken (HTTP/content),
    # since a filtered path is not a repo defect.
    broken = any(not l.get("ok") for l in report["layers"]
                 if l["layer"].startswith(("4", "5")))
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
