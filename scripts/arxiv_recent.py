#!/usr/bin/env python3
import re, sys, urllib.request

cat = sys.argv[1] if len(sys.argv) > 1 else "cs.LG"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
url = ("http://export.arxiv.org/api/query?search_query=cat:" + cat +
       "&sortBy=submittedDate&sortOrder=descending&max_results=" + str(n))
raw = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")


def tag(entry, t):
    m = re.search("<" + t + ">(.*?)</" + t + ">", entry, re.S)
    return " ".join(m.group(1).split()) if m else ""


for entry in raw.split("<entry>")[1:]:
    print(tag(entry, "published")[:10], "|", tag(entry, "id").split("/")[-1])
    print("  T:", tag(entry, "title"))
    print("  S:", tag(entry, "summary")[:280])
    print()
