#!/usr/bin/env python3
"""Push current HEAD without staging anything (shared checkout safe)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish  # reuse token/proxy/branch logic


def main() -> int:
    token = publish.load_token()
    # Direct github.com times out from this host; go through the same
    # gh-proxy mirror publish.py uses.
    host = publish.PROXY.split("//", 1)[1]
    url = "https://x-access-token:" + token + "@" + host + "/" + publish.SLUG + ".git"
    ref = "HEAD:" + publish.BRANCH
    p = publish.run(["git", "push", url, ref], token, timeout=240)
    ok = p.returncode == 0
    err = "" if ok else ((p.stderr or "") + (p.stdout or ""))[:400]
    print({"pushed": ok, "branch": publish.BRANCH, "error": err})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
