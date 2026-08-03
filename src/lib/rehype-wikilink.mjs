/**
 * rehype plugin: link the first mention of each known concept term.
 *
 * Runs over the HTML tree so it can see structure and skip code, headings,
 * existing links and KaTeX output. See src/lib/autolink.ts for the typed
 * reference implementation of the same algorithm.
 */
import { loadTerms } from './concept-terms.mjs';

/**
 * `blockquote` is skipped because quoted primary text is evidence, not our
 * prose: an alias table built for our glossary must not silently reinterpret
 * someone else's words. Satoshi's "the block cannot be changed" was linked to
 * /concepts/change-output (Bitcoin 找零) on that rule alone.
 */
const SKIP = new Set([
  'a', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'script', 'style', 'blockquote',
]);

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function isCjk(s) {
  return /[\u4e00-\u9fff]/.test(s);
}

/** Longest-first alternation: 'KV cache' must beat 'cache'. */
function buildMatcher(terms) {
  const parts = [...terms]
    .sort((a, b) => b.text.length - a.text.length)
    .map((t) => (isCjk(t.text) ? escapeRe(t.text) : '\\b' + escapeRe(t.text) + '\\b'));
  return new RegExp('(' + parts.join('|') + ')', 'iu');
}

export default function rehypeWikilink(options = {}) {
  const base = options.base ?? '/';
  const prefix = base.endsWith('/') ? base : base + '/';

  return (tree, file) => {
    const terms = loadTerms();
    if (terms.length === 0) return;

    // Don't let a concept page link to itself.
    const self = String(file?.history?.[0] ?? '').match(/concepts\/([^/]+)\.md$/);
    const selfId = self ? self[1] : null;
    const pool = terms.filter((t) => t.id !== selfId);
    if (pool.length === 0) return;

    const matcher = buildMatcher(pool);
    const used = new Set();

    const lookup = (surface) => {
      const low = surface.toLowerCase();
      return pool.find((t) => t.text.toLowerCase() === low);
    };

    const linkNode = (term, surface) => ({
      type: 'element',
      tagName: 'a',
      properties: {
        href: prefix + 'concepts/' + term.id,
        className: ['wikilink'],
        title: term.hint || undefined,
        'data-term': term.id,
      },
      children: [{ type: 'text', value: surface }],
    });

    const splitText = (value) => {
      const out = [];
      let rest = value;
      while (rest) {
        const m = matcher.exec(rest);
        if (!m) break;
        const term = lookup(m[1]);
        if (!term || used.has(term.id)) {
          // Already linked once, or unknown: keep scanning past it.
          const cut = m.index + m[1].length;
          out.push({ type: 'text', value: rest.slice(0, cut) });
          rest = rest.slice(cut);
          continue;
        }
        if (m.index > 0) out.push({ type: 'text', value: rest.slice(0, m.index) });
        out.push(linkNode(term, m[1]));
        used.add(term.id);
        rest = rest.slice(m.index + m[1].length);
      }
      if (rest) out.push({ type: 'text', value: rest });
      return out.length > 1 ? out : null;
    };

    const walk = (node, inSkip) => {
      if (!node.children) return;
      const next = [];
      let changed = false;
      for (const child of node.children) {
        if (!inSkip && child.type === 'text') {
          const parts = splitText(child.value);
          if (parts) {
            next.push(...parts);
            changed = true;
            continue;
          }
        }
        if (child.type === 'element') {
          const cls = child.properties?.className;
          const classList = Array.isArray(cls) ? cls : cls ? [cls] : [];
          const isMath = classList.some((c) => String(c).startsWith('katex'));
          walk(child, inSkip || SKIP.has(child.tagName) || isMath);
        }
        next.push(child);
      }
      if (changed) node.children = next;
    };

    walk(tree, false);
  };
}
