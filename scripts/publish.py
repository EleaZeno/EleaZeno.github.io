#!/usr/bin/env python3
"""Commit and push the site, working around this machine's network limits.

Direct github.com git operations time out here; only the gh-proxy.com mirror
and api.github.com are reachable. Credentials come from ~/.hermes/.env
(GITHUB_TOKEN) and are never written into .git/config or echoed to stdout.

Usage:
    publish.py [--message "..."] [--dry-run] [--remote-check]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = Path(os.environ.get("HERMES_ENV", "/root/.hermes/.env"))
SLUG = os.environ.get("BLOG_REPO", "EleaZeno/EleaZeno.github.io")
BRANCH = os.environ.get("BLOG_BRANCH", "master")
PROXY = os.environ.get("GIT_PROXY_BASE", "https://gh-proxy.com/https://github.com")


def load_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        return tok
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "GITHUB_TOKEN":
                return v.strip().strip('"').strip("'")
    raise SystemExit("no GITHUB_TOKEN found (env or ~/.hermes/.env)")


def run(args: list[str], token: str = "", **kw) -> subprocess.CompletedProcess:
    """Run git, scrubbing the token from any captured output."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("cwd", REPO)
    proc = subprocess.run(args, **kw)
    if token:
        if proc.stdout:
            proc.stdout = proc.stdout.replace(token, "***")
        if proc.stderr:
            proc.stderr = proc.stderr.replace(token, "***")
    return proc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Commit and push the blog")
    ap.add_argument("--message")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--remote-check", action="store_true",
                    help="only verify remote reachability, change nothing")
    args = ap.parse_args(argv)

    token = load_token()
    push_url = f"https://x-access-token:{token}@{PROXY.split('://', 1)[1]}/{SLUG}.git"
    read_url = f"{PROXY}/{SLUG}.git"

    if args.remote_check:
        p = run(["git", "ls-remote", "--heads", read_url, BRANCH], token, timeout=90)
        out = (p.stdout or "").strip()
        json.dump({"reachable": p.returncode == 0, "head": out.split()[0][:12] if out else None,
                   "stderr": (p.stderr or "")[:200]},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if p.returncode == 0 else 1

    status = run(["git", "status", "--porcelain"], token)
    changes = [l for l in status.stdout.splitlines() if l.strip()]
    if not changes:
        json.dump({"committed": False, "reason": "nothing to commit"},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    # Describe the commit by what actually changed.
    # Count only added content, not deletions/renames, so the message
    # reflects what was published rather than what churned.
    def added(prefix: str) -> list[str]:
        return [l for l in changes
                if prefix in l and l[:2].strip() in ("A", "??", "AM")]

    posts = added("src/content/posts/")
    dreams = added("src/content/dreams/")
    if args.message:
        msg = args.message
    else:
        bits = []
        if posts:
            bits.append(f"{len(posts)} 篇文章")
        if dreams:
            bits.append(f"{len(dreams)} 则夜间笔记")
        msg = f"content: {date.today().isoformat()} " + (" + ".join(bits) if bits else "站点更新")

    if args.dry_run:
        json.dump({"would_commit": changes, "message": msg},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    run(["git", "add", "-A"], token)
    commit = run(
        ["git", "-c", "user.name=Hermes Agent",
         "-c", "user.email=hermes@users.noreply.github.com",
         "commit", "-m", msg],
        token,
    )
    if commit.returncode != 0:
        print(commit.stdout + commit.stderr, file=sys.stderr)
        return 1

    push = run(["git", "push", push_url, f"HEAD:{BRANCH}"], token, timeout=240)
    sha = run(["git", "rev-parse", "HEAD"], token).stdout.strip()[:12]

    json.dump(
        {
            "committed": True,
            "message": msg,
            "sha": sha,
            "pushed": push.returncode == 0,
            "push_error": None if push.returncode == 0 else (push.stderr or "")[:400],
            "files": len(changes),
        },
        sys.stdout, ensure_ascii=False, indent=2,
    )
    sys.stdout.write("\n")
    return 0 if push.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
