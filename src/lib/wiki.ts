import { getCollection, type CollectionEntry } from 'astro:content';
import { getClassics } from './classics';
import type { Term } from './autolink';

export type Concept = CollectionEntry<'concepts'>;

/** All concept pages, alphabetical by title. */
export async function getConcepts(): Promise<Concept[]> {
  const all = await getCollection('concepts');
  return all.sort((a, b) => a.data.title.localeCompare(b.data.title, 'zh-Hans-CN'));
}

/**
 * Flatten concepts into linkable surface forms: the title plus every alias.
 * Aliases are what let one page absorb '推理'/'inference'/'KV cache'/'KV 缓存'.
 */
export async function getTerms(): Promise<Term[]> {
  const concepts = await getConcepts();
  const terms: Term[] = [];
  for (const c of concepts) {
    const surfaces = [c.data.title, ...c.data.aliases];
    for (const s of surfaces) {
      const text = s.trim();
      if (text) terms.push({ id: c.id, text, hint: c.data.oneLiner });
    }
  }
  return terms;
}

/** Does this text mention the concept (title or any alias)? */
function mentions(text: string, c: Concept): boolean {
  const hay = text.toLowerCase();
  return [c.data.title, ...c.data.aliases].some((s) => {
    const needle = s.trim().toLowerCase();
    return needle.length >= 2 && hay.includes(needle);
  });
}

export interface Backlink {
  id: string;
  title: string;
  kind: 'post' | 'concept';
  pubDate?: Date;
}

/**
 * Which posts and concepts reference this concept.
 *
 * Computed from the raw body rather than from the rendered links: the
 * autolinker only marks the first mention, but a page that discusses a term
 * five times further down is still a genuine inbound reference.
 */
export async function backlinksFor(
  concept: Concept,
  posts: Array<CollectionEntry<'posts'>>,
  concepts: Concept[],
): Promise<Backlink[]> {
  const out: Backlink[] = [];
  for (const p of posts) {
    const hay = `${p.data.title} ${p.data.description} ${p.body ?? ''} ${p.data.take ?? ''}`;
    if (mentions(hay, concept)) {
      out.push({ id: p.id, title: p.data.title, kind: 'post', pubDate: p.data.pubDate });
    }
  }
  for (const c of concepts) {
    if (c.id === concept.id) continue;
    const hay = `${c.data.oneLiner} ${c.body ?? ''}`;
    const declared = c.data.related.includes(concept.id);
    if (declared || mentions(hay, concept)) {
      out.push({ id: c.id, title: c.data.title, kind: 'concept' });
    }
  }
  return out;
}
/**
 * Reader-facing labels for the depth marker on each concept.
 *
 * Keys must match the `level` enum in content.config.ts. They previously read
 * primer/working/deep while the schema allowed intro/core/deep, so intro and
 * core concepts rendered a blank label.
 */
export const LEVEL_LABELS: Record<string, string> = {
  intro: '入门',
  core: '核心',
  deep: '深入',
};

/**
 * A page that mentions a concept.
 *
 * Both day-to-day posts and classics deconstructions cite terms, and a reader
 * landing on a concept wants either kind. Carrying the collection here lets the
 * concept page build the right URL without a second lookup.
 */
export interface Mention {
  kind: 'post' | 'classic';
  id: string;
  title: string;
  date: Date;
}

export interface GraphNode {
  concept: Concept;
  /** Posts and classics that mention this term, newest first. */
  mentionedBy: Mention[];
  /** Declared neighbours plus concepts that mention this one. */
  related: Concept[];
}

/**
 * Build the whole wiki graph once.
 *
 * Called from getStaticPaths, so doing it in one pass keeps the build from
 * re-scanning every post per concept.
 */
export async function conceptGraph(): Promise<Map<string, GraphNode>> {
  const concepts = await getConcepts();
  const posts = (await getCollection('posts'))
    .filter((p) => import.meta.env.DEV || !p.data.draft)
    .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
  const classics = await getClassics();

  const byId = new Map(concepts.map((c) => [c.id, c]));
  const graph = new Map<string, GraphNode>();

  for (const c of concepts) {
    const mentionedBy: Mention[] = [
      ...posts
        .filter((p) =>
          mentions(`${p.data.title} ${p.data.description} ${p.body ?? ''} ${p.data.take ?? ''}`, c),
        )
        .map((p) => ({
          kind: 'post' as const,
          id: p.id,
          title: p.data.title,
          date: p.data.pubDate,
        })),
      ...classics
        .filter((e) =>
          mentions(
            `${e.data.title} ${e.data.originalTitle} ${e.data.description} ${e.body ?? ''}`,
            c,
          ),
        )
        .map((e) => ({
          kind: 'classic' as const,
          id: e.id,
          title: e.data.title,
          date: e.data.pubDate,
        })),
    ].sort((a, b) => b.date.valueOf() - a.date.valueOf());

    // Declared neighbours first (curated), then discovered ones.
    const related: Concept[] = [];
    const seen = new Set<string>([c.id]);
    for (const id of c.data.related) {
      const n = byId.get(id);
      if (n && !seen.has(id)) {
        related.push(n);
        seen.add(id);
      }
    }
    for (const other of concepts) {
      if (seen.has(other.id)) continue;
      // Symmetric: if they name us, or their body mentions us, surface them.
      const theyName = other.data.related.includes(c.id);
      const theyMention = mentions(`${other.data.oneLiner} ${other.body ?? ''}`, c);
      if (theyName || theyMention) {
        related.push(other);
        seen.add(other.id);
      }
    }

    graph.set(c.id, { concept: c, mentionedBy, related });
  }
  return graph;
}
