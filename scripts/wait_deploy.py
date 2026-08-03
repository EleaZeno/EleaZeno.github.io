#!/usr/bin/env python3
"""Wait for the Pages deploy of HEAD's exact sha.

The runs listing is newest-first; matching the wrong row once reported success
for a commit whose deploy had actually failed. Compare head_sha explicitly.
"""
import json, subprocess, sys, time, urllib.request

REPO = "EleaZeno/EleaZeno.github.io"
sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                     text=True, check=True).stdout.strip()
print("waiting for", sha[:12], flush=True)

url = "https://api.github.com/repos/%s/actions/runs?per_page=10" % REPO
for attempt in range(1, 25):
    time.sleep(20)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "elea-notes"})
        runs = json.load(urllib.request.urlopen(req, timeout=30))["workflow_runs"]
    except Exception as exc:
        print("attempt %d: fetch error %s" % (attempt, exc), flush=True)
        continue
    row = next((r for r in runs if r["head_sha"] == sha), None)
    if row is None:
        print("attempt %d: run not created yet" % attempt, flush=True)
        continue
    print("attempt %d: %s %s" % (attempt, row["status"], row["conclusion"]), flush=True)
    if row["status"] == "completed":
        sys.exit(0 if row["conclusion"] == "success" else 1)
print("timed out waiting for deploy")
sys.exit(2)
