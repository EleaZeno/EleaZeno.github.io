import { getCollection, type CollectionEntry } from 'astro:content';

export type Classic = CollectionEntry<'classics'>;

const isProd = import.meta.env.PROD;

/** Published deconstructions, newest first. Mirrors getPublishedPosts. */
export async function getClassics(): Promise<Classic[]> {
  const classics = await getCollection('classics', ({ data }) => !(isProd && data.draft));
  return classics.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}
