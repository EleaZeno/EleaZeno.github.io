import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getPublishedPosts } from '../lib/posts';
import { url } from '../lib/url';
import { SITE } from '../site.config';

export async function GET(context: APIContext) {
  const posts = await getPublishedPosts();
  return rss({
    title: SITE.title,
    description: SITE.description,
    // context.site is the bare origin; item links and <link> must carry the
    // base path or every feed entry 404s on a project site.
    site: new URL(url(''), context.site!),
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      categories: post.data.tags,
      link: `posts/${post.id}/`,
    })),
    customData: `<language>${SITE.lang}</language>`,
  });
}
