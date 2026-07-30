/**
 * Build-time term auto-linking for the wiki layer.
 *
 * The wiki only compounds if articles link their jargon to a definition, and
 * doing that by hand rots immediately. This visits the rendered HTML tree and
 * links the FIRST mention of each known term, then leaves the rest alone so
 * the prose stays readable.
 *
 * Deliberate constraints:
 *  - never inside <a>, <code>, <pre>, headings, or KaTeX output
 *  - one link per term per page
 *  - longest term wins, so 'KV cache' beats 'cache'
 *  - a page never links to itself
 */
import type { Root, Element, Text, Parent } from 'hast';

export interface Term {
  /** Slug of the concept page this term points at. */
  id: string;
  /** Surface form to match in prose. */
  text: string;
  /** One-line definition, used as the link title (native hover tooltip). */
  hint: string;
}

const SKIP_TAGS = new Set(['a', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'script', 'style']);

/** CJK has no word boundaries, so \\b is useless for Chinese terms. */
function isCjk(s: string): boolean {
  return /[\u4e00-\u9fff]/.test(s);
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * One regex for all terms, longest first so the greedy alternation prefers
 * the most specific match. Latin terms get word boundaries; CJK terms cannot.
 */
function buildMatcher(terms: Term[]): RegExp {
  const parts = [...terms]
    .sort((a, b) => b.text.length - a.text.length)
    .map((t) => (isCjk(t.text) ? escapeRe(t.text) : `\\b${escapeRe(t.text)}\\b`));
  return new RegExp(`(${parts.join('|')})`, 'iu');
}

export interface AutolinkOptions {
  terms: Term[];
  /** Concept id of the current page, so it never links to itself. */
  selfId?: string;
  /** Prefix for concept URLs, base-path aware. */
  base?: string;
}

export function autolink(tree: Root, opts: AutolinkOptions): number {
  const terms = opts.terms.filter((t) => t.id !== opts.selfId && t.text.length >= 2);
  if (terms.length === 0) return 0;

  const byText = new Map<string, Term>();
  for (const t of terms) byText.set(t.text.toLowerCase(), t);
  const matcher = buildMatcher(terms);
  const used = new Set<string>();
  const base = opts.base ?? '/';
  let linked = 0;

  function visit(node: Parent, inSkip: boolean): void {
    const kids = node.children ?? [];
    for (let i = 0; i < kids.length; i++) {
      const child = kids[i];
      if (child.type === 'element') {
        const el = child as Element;
        const cls = el.properties?.className;
        const classList = Array.isArray(cls) ? cls.map(String) : [];
        const isMath = classList.some((c) => c.startsWith('katex'));
        visit(el, inSkip || SKIP_TAGS.has(el.tagName) || isMath);
      } else if (child.type === 'text' && !inSkip) {
        const replaced = linkText(child as Text);
        if (replaced) {
          kids.splice(i, 1, ...replaced);
          i += replaced.length - 1;
        }
      }
    }
  }

  /** Split one text node into [text, <a>, text...] for unused terms. */
  function linkText(node: Text): Array<Text | Element> | null {
    let rest = String(node.value);
    const out: Array<Text | Element> = [];
    let hit = false;

    while (rest) {
      const m = matcher.exec(rest);
      if (!m || m.index === undefined) break;
      const surface = m[0];
      const term = byText.get(surface.toLowerCase());
      if (!term || used.has(term.id)) {
        // Already linked once on this page: keep the text, move past it.
        const cut = m.index + surface.length;
        out.push({ type: 'text', value: rest.slice(0, cut) });
        rest = rest.slice(cut);
        continue;
      }
      used.add(term.id);
      hit = true;
      linked++;
      if (m.index > 0) out.push({ type: 'text', value: rest.slice(0, m.index) });
      out.push({
        type: 'element',
        tagName: 'a',
        properties: {
          href: `${base}concepts/${term.id}`,
          className: ['wikilink'],
          title: term.hint,
        },
        children: [{ type: 'text', value: surface }],
      });
      rest = rest.slice(m.index + surface.length);
    }
    if (!hit) return null;
    if (rest) out.push({ type: 'text', value: rest });
    return out;
  }

  visit(tree, false);
  return linked;
}
