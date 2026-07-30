#!/usr/bin/env python3
import glob, json, os, re, sys
D='src/content/concepts/'
A='src/content/posts/'

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
    for p in sorted(glob.glob(D+'*.md')):
        i=os.path.basename(p)[:-3]
        d,b=fm(open(p,encoding='utf-8').read())
        ids[i]=d
        body[i]=b
    posts={}
    for p in sorted(glob.glob(A+'*.md')):
        posts[os.path.basename(p)[:-3]]=open(p,encoding='utf-8').read()
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
        if '## 一句话' not in b:
            errs.append('missing 一句话 opener section')
        names=[d.get('title','').strip().strip('"')]
        names+=d.get('aliases_inline',[])
        cited=any(any(n and n in t for n in names) for t in posts.values())
        linked=any(i in (o.get('related_inline') or []) for j,o in ids.items() if j!=i)
        if not cited and not linked:
            errs.append('orphan: no article mentions it and no concept links to it')
        if errs:
            prob[i]=errs
    out={'concepts':len(ids),'posts':len(posts),'problems':prob}
    json.dump(out,sys.stdout,ensure_ascii=False,indent=2)
    print()
    return 1 if prob else 0


if __name__=='__main__':
    raise SystemExit(main())
