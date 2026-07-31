import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getClassics } from '../lib/classics';
import { getDreams, getPublishedPosts } from '../lib/posts';
import { url } from '../lib/url';
import { SITE } from '../site.config';

/**
 * One feed for everything worth reading.
 *
 * Posts and classics are different shapes but the same promise to a subscriber:
 * something new to read. Splitting them into two feeds would mean the
 * deconstructions — the slowest, most expensive pieces to write — reach nobody
 * who subscribed before the collection existed.
 */
export async function GET(context: APIContext) {
  const posts = await getPublishedPosts();
  const classics = await getClassics();
  const dreams = await getDreams();

  const items = [
    ...posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: url(`posts/${post.id}/`),
      categories: post.data.tags,
    })),
    ...classics.map((entry) => ({
      title: entry.data.title,
      description: entry.data.description,
      pubDate: entry.data.pubDate,
      link: url(`classics/${entry.id}/`),
      categories: ['经典拆解', entry.data.field],
    })),
    // Nightly notes carry a summary rather than a description, and they are
    // explicitly unverified — the category says so, so a subscriber can tell
    // them apart from a post without opening the link.
    ...dreams.map((entry) => ({
      title: entry.data.title,
      description: entry.data.summary,
      pubDate: entry.data.date,
      link: url(`dreams/${entry.id}/`),
      categories: ['夜间笔记'],
    })),
  ].sort((a, b) => b.pubDate.valueOf() - a.pubDate.valueOf());

  return rss({
    title: SITE.title,
    description: SITE.description,
    // context.site has no path component; add the base path explicitly.
    site: new URL(url(''), context.site).toString(),
    customData: `<language>${SITE.lang}</language>`,
    items,
  });
}
