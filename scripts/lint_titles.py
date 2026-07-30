#!/usr/bin/env python3
"""Reject clickbait and vague titles before publish.

A title should let the reader decide if the piece is worth their time, in the
terms of the field. Hook phrasing (second person, suspense, exclamation) and
bare superlatives fail. Run from the repo root; exit 1 = fix before publishing.
"""
from __future__ import annotations

import glob
import json
import re
import sys

POSTS = 'src/content/posts/*.md'

# Hook/vague constructions that carry no information about the subject.
BANNED = [
    '震惊', '爆了', '炸了', '太强', '逆天', '碾压', '吊打', '封神',
    '你不知道', '你必须', '看完就懂', '一文读懂', '手把手',
    '究竟', '到底是什么', '真相', '揭秘', '内幕',
    '厉害了', '没想到', '竟然', '居然', '万万没想到',
]

def frontmatter(text):
    if not text.startswith('---'):
        return {}
    end = text.find(chr(10) + '---', 3)
    head = text[3:end] if end != -1 else ''
    out = {}
    for line in head.splitlines():
        m = re.match(r'^(\w+):\s*(.*)$', line)
        if m:
            v = m.group(2).strip()
            if len(v) > 1 and v[0] == v[-1] and v[0] in '\'"':
                v = v[1:-1]
            out[m.group(1)] = v
    return out


def check(title, desc):
    problems = []
    low = title.lower()
    for b in BANNED:
        if b in title:
            problems.append('hook phrase: ' + b)
    # First-person narration belongs in the body, not the headline.
    for w in ['我是怎么', '我去', '我把', '去核一条', '带你', '教你', '聊聊', '说说']:
        if w in title:
            problems.append('narrating the author instead of the finding: ' + w)
    if title.endswith('?') or title.endswith('？'):
        problems.append('title is a question; state the finding instead')
    if '!' in title or '！' in title:
        problems.append('exclamation mark')
    # A professional title names its subject: expect a proper noun, a number,
    # or a technical term. Pure prose with none of those is usually a hook.
    has_anchor = bool(re.search(r'[A-Za-z]{2,}|[0-9]', title))
    if not has_anchor:
        problems.append('no technical anchor (term, name, or figure) in title')
    if len(title) > 46:
        problems.append('title too long (' + str(len(title)) + ' chars, max 46)')
    if len(title) < 8:
        problems.append('title too short')
    if not desc:
        problems.append('missing description')
    elif len(desc) < 24:
        problems.append('description too thin')
    return problems


def main():
    bad = {}
    n = 0
    for path in sorted(glob.glob(POSTS)):
        fm = frontmatter(open(path, encoding='utf-8').read())
        if fm.get('draft') == 'true':
            continue
        n += 1
        problems = check(fm.get('title', ''), fm.get('description', ''))
        if problems:
            bad[path] = {'title': fm.get('title', ''), 'problems': problems}
    print(json.dumps({'checked': n, 'failing': bad}, ensure_ascii=False, indent=2))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
