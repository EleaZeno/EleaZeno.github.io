import { getCollection, type CollectionEntry } from 'astro:content';

export type Post = CollectionEntry<'posts'>;
export type Dream = CollectionEntry<'dreams'>;

const isProd = import.meta.env.PROD;

/** Published posts, newest first. Drafts are hidden in production only. */
export async function getPublishedPosts(): Promise<Post[]> {
  const posts = await getCollection('posts', ({ data }) => !(isProd && data.draft));
  return posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}

/** Nightly reflections, newest first, then by cycle. */
export async function getDreams(): Promise<Dream[]> {
  const dreams = await getCollection('dreams');
  return dreams.sort(
    (a, b) => b.data.date.valueOf() - a.data.date.valueOf() || b.data.cycle - a.data.cycle,
  );
}

export function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Tag -> count, sorted by count desc then name, for stable output. */
export function tagCounts(posts: Post[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const p of posts) {
    for (const t of p.data.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

export const DOMAIN_LABELS: Record<string, string> = {
  ai: 'AI',
  crypto: '加密与分布式',
  systems: '系统与工程',
  theory: '理论',
  other: '其他',
};

/** Rough reading time in minutes; CJK counts by character, Latin by word. */
export function readingMinutes(body: string): number {
  const cjk = (body.match(/[\u4e00-\u9fff]/g) ?? []).length;
  const latin = (body.replace(/[\u4e00-\u9fff]/g, ' ').match(/\b\w+\b/g) ?? []).length;
  return Math.max(1, Math.round(cjk / 400 + latin / 220));
}
