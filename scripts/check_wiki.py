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

# Terms we consider load-bearing enough that a reader who does not know them
# is stuck. Hand-curated on purpose: a generic noun-phrase extractor over
# Chinese prose produces mostly noise, and the point of this list is to be
# short enough that every entry is worth a page. Add a term when an article
# starts leaning on it; the checker then nags until the page exists.
WATCH_TERMS=(
    '区块头','区块','时间戳服务器','时间戳链','时间戳','最长链','算力','全节点',
    '轻节点','节点','难度','目标值','分叉','孤块','泊松分布','泊松','赌徒破产',
    '随机游走','女巫攻击','拜占庭将军','51%','剪枝','找零','手续费','币基交易',
    '椭圆曲线','密钥对','诚实节点','矿工','激励','共识','熵','信息量','信道容量',
    '压缩率','前缀码','互信息','素数','多项式时间','确定性算法','图灵测试',
    '模仿游戏','中文屋','意向性','强人工智能','间隔效应','交错练习','提取练习',
    '存储强度','提取强度','必要难度',
)

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
        # The opening must not be a definition dump. Two shapes pass:
        #  (a) legacy glossary entries that lead with '## 一句话';
        #  (b) Petzold-style entries that open on a concrete difficulty and
        #      only name the concept afterwards.
        # (b) has no fixed wording -- the hook is written fresh each time -- so
        # we check it structurally: there is a '## 机制' section (the mechanism
        # is stated explicitly somewhere) and the first heading is not it.
        heads=re.findall(r'^## +(.+)$', b, re.M)
        if heads:
            has_oneliner = any(h.strip().startswith('一句话') for h in heads)
            has_mech = any(h.strip().startswith('机制') or '机制' in h for h in heads)
            first_is_mech = heads[0].strip().startswith('机制')
            if not has_oneliner and not (has_mech and not first_is_mech):
                errs.append('opener neither 一句话 nor problem-first (needs a 机制 section after a hook)')
        else:
            errs.append('no section headings at all')
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
        for r in d.get('prerequisites_inline',[]):
            if r and r not in ids:
                prob.setdefault(i,[]).append('dangling prerequisite: '+r)

    # Reverse check: terms the prose leans on that have no page yet.
    #
    # The orphan check above asks "is this page reachable?". It cannot see the
    # opposite and more common failure: an article names twelve technical terms
    # and only four are explained on-site, so a reader hits "你应该知道的事"
    # followed by a list of words nobody defined. That gap is invisible unless
    # someone reads the whole article, which is exactly the review that does not
    # scale -- so the build reports it instead.
    #
    # Advisory, not fatal: breadth is filled deliberately over time, and a hard
    # failure here would block every draft that mentions a term in passing.
    covered=set()
    for i,d in ids.items():
        for n in [d.get('title','').strip().strip('"'), i]+d.get('aliases_inline',[]):
            if n:
                covered.add(n)
    todo={}
    for p,t in posts.items():
        _,b=fm(t)
        # Prose only: quoted primary text and code are not ours to gloss.
        b=re.sub(r'```[\s\S]*?```','',b)
        b=re.sub(r'(?m)^>.*$','',b)
        b=re.sub(r'`[^`]*`','',b)
        hits={}
        for term in WATCH_TERMS:
            n=b.count(term)
            if n and not any(term in c or c in term for c in covered):
                hits[term]=n
        if hits:
            todo[p]=dict(sorted(hits.items(), key=lambda kv:-kv[1]))

    # Alias hygiene. The autolinker (src/lib/rehype-wikilink.mjs) resolves a
    # matched string by longest-first alternation and nothing else, so when two
    # concepts claim the same alias the winner is whatever order loadTerms()
    # happens to return -- decided silently, with no warning. Two real mis-links
    # came from this class in two days: "change" pointed at 找零 inside an
    # English quotation, and "51" (an alias of 51% 攻击) fired on a bare 字数.
    # Nothing else in the chain can catch it: every other gate reads source
    # text, and the source text is innocent -- the defect is in the alias table.
    # The pool the autolinker actually builds is [title, *aliases] (see
    # concept-terms.mjs loadTerms). Comparing aliases only against aliases
    # therefore misses the whole title-vs-alias half of the same defect: an
    # alias that duplicates ANOTHER concept's title collides just as hard, and
    # 18 of 70 concepts do not list their own title among their aliases, so the
    # collision is invisible unless titles go into the same bucket. Verified by
    # injection: giving agent.md the alias 纠删码 (erasure-coding's title)
    # mis-linked 4 pages to /concepts/agent while every gate stayed green.
    # Which one wins depends on readdirSync order, so the same table can be
    # harmless today and wrong after an unrelated file is added.
    ambiguous = {}
    for i, d in ids.items():
        surfaces = list(d.get('aliases_inline', []))
        t = d.get('title', '').strip().strip('"')
        if t:
            surfaces.append(t)
        for a in set(s for s in surfaces if s):
            ambiguous.setdefault(a, []).append(i)
    for a, owners in sorted(ambiguous.items()):
        if len(owners) > 1:
            prob.setdefault('alias_claimed_twice', []).append(
                '%r claimed by %s; the autolinker picks one arbitrarily'
                % (a, ' and '.join(sorted(owners))))
    for i, d in ids.items():
        for a in d.get('aliases_inline', []):
            # A pure-digit alias matches any occurrence of those digits --
            # a percentage, a count, a year. Never what the author meant.
            if a and re.fullmatch(r'[0-9]+', a):
                prob.setdefault('alias_bare_number', []).append(
                    '%s: alias %r matches any digits in prose' % (i, a))

    out={'concepts':len(ids),'posts':len(posts),'problems':prob,
         'uncovered_terms':todo}
    json.dump(out,sys.stdout,ensure_ascii=False,indent=2)
    print()
    return 1 if prob else 0


if __name__=='__main__':
    raise SystemExit(main())
