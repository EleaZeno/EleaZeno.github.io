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
    // context.site has no path component; add the base path explicitly.
    site: new URL(url(''), context.site).toString(),
    customData: `<language>${SITE.lang}</language>`,
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: url(`posts/${post.id}/`),
      categories: post.data.tags,
    })),
  });
}
