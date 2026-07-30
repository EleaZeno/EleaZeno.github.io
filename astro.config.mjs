// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeWikilink from './src/lib/rehype-wikilink.mjs';
import rehypeClassicAnchors from './src/lib/rehype-classic-anchors.mjs';
import rehypeTableScroll from './src/lib/rehype-table-scroll.mjs';

// User site: https://eleazeno.github.io lives at the root, so BASE_PATH is '/'.
// Both are still env-driven so the same tree can be built as a project site
// (BASE_PATH=/repo) without code changes — and so check_links.py can verify
// the base-path handling under both shapes.
const SITE_URL = process.env.SITE_URL ?? 'https://eleazeno.github.io';
const BASE_PATH = process.env.BASE_PATH ?? '/';

export default defineConfig({
  site: SITE_URL,
  base: BASE_PATH,
  trailingSlash: 'ignore',
  // extendMarkdownConfig (the default) makes .mdx reuse the markdown
  // pipeline below, so math and wiki-links behave identically in both.
  integrations: [sitemap(), mdx()],
  markdown: {
    remarkPlugins: [remarkMath],
    // KaTeX renders to MathML + styled HTML at build time: no client-side JS,
    // no layout shift, and it still degrades to readable MathML if CSS fails.
    rehypePlugins: [
      [rehypeKatex, { output: 'htmlAndMathml', throwOnError: false }],
      // After KaTeX so math nodes are already built and get skipped.
      [rehypeWikilink, { base: BASE_PATH }],
      // Section ids for classics, so annotations can be deep-linked.
      rehypeClassicAnchors,
      // Wrap wide tables so they scroll instead of widening the page on phones.
      rehypeTableScroll,
    ],
    shikiConfig: {
      themes: { light: 'github-light', dark: 'github-dark-dimmed' },
      wrap: true,
    },
  },
  build: { format: 'directory' },
});
