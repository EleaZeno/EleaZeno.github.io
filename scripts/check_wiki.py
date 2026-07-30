#!/usr/bin/env python3
import glob, json, os, re, sys
D='src/content/concepts/'
# Every collection whose prose may cite a concept. Classics deconstructions
# lean on the wiki harder than posts do (they declare prerequisites), so
# leaving them out here made the orphan check blind to real usage.
ARTICLE_DIRS=('src/content/posts/','src/content/classics/','src/content/dreams/')

def fm(t):
    if not t.startswith('---'):
        return {}, t
    e=t.find('---',3)
    h,b=t[3:e],t[e+3:]
    d={}
    k=None
    for ln in h.splitlines():
        m=re.match(r'([A-Za-z_]+):\s*(.*)$', ln)
        if m:
            k=m.group(1); v=m.group(2).strip()
            d[k]=v
            if v.startswith('[') and v.endswith(']'):
                d[k+'_inline']=[x.strip().strip('"') for x in v[1:-1].split(',') if x.strip()]
        elif ln.strip().startswith('- ') and k:
            d.setdefault(k+'_list',[]).append(ln.strip()[2:].strip().strip('"'))
    return d, b

# Real failure mode: a definition that opens by naming a category
# ('X 是一种 Y 算法') instead of saying what it does for the reader.
JARGON_OPENERS=('是一种','是指','指的是','一种用于','一类')

def main():
    ids={}
    body={}
    # .mdx included: concepts carrying <Sidenote> must be MDX (see content.config.ts).
    for p in sorted(glob.glob(D+'*.md')+glob.glob(D+'*.mdx')):
        i=os.path.splitext(os.path.basename(p))[0]
        d,b=fm(open(p,encoding='utf-8').read())
        ids[i]=d
        body[i]=b
    posts={}
    for A in ARTICLE_DIRS:
        # .mdx too: classics embed components, so they are authored as MDX.
        for p in sorted(glob.glob(A+'*.md'))+sorted(glob.glob(A+'*.mdx')):
            posts[p]=open(p,encoding='utf-8').read()
    prob={}
    for i,d in ids.items():
        errs=[]
        for r in d.get('related_inline',[]):
            if r and r not in ids:
                errs.append('dangling related: '+r)
        s=d.get('oneLiner','').strip().strip('"')
        if not s:
            errs.append('missing oneLiner')
        elif len(s)>60:
            errs.append('summary too long (%d chars); one plain sentence' % len(s))
        elif any(j in s[:14] for j in JARGON_OPENERS):
            errs.append('summary opens with jargon, not plain language')
        b=body.get(i,'')
        heads=[h.strip() for h in re.findall(r'(?m)^##\s+(.+)$', b)]
        has_oneliner='## 一句话' in b
        has_mech=any('机制' in h for h in heads)
        if not has_oneliner and not has_mech:
            errs.append('opener neither 一句话 nor problem-first (needs a 机制 section after a hook)')
        names=[d.get('title','').strip().strip('"')]
        names+=d.get('aliases_inline',[])
        cited=any(any(n and n in t for n in names) for t in posts.values())
        # Being listed under a classic's `prerequisites:` is explicit usage
        # even when the concept's display name never appears in the prose.
        declared=any(i in t for t in posts.values())
        linked=any(i in (o.get('related_inline') or []) for j,o in ids.items() if j!=i)
        if not cited and not linked and not declared:
            errs.append('orphan: no article mentions it and no concept links to it')
        if errs:
            prob[i]=errs
    out={'concepts':len(ids),'posts':len(posts),'problems':prob}
    json.dump(out,sys.stdout,ensure_ascii=False,indent=2)
    print()
    return 1 if prob else 0


if __name__=='__main__':
    raise SystemExit(main())
