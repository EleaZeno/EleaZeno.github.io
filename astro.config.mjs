// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

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
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      themes: { light: 'github-light', dark: 'github-dark-dimmed' },
      wrap: true,
    },
  },
  build: { format: 'directory' },
});
