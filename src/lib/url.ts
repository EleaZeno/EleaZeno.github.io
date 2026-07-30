/**
 * Base-path-aware URL helpers.
 *
 * On a project site the deployment lives under `/<repo>/`, so every internal
 * href must carry that prefix. `new URL('/archive', Astro.url)` would resolve
 * against the origin and silently drop it, producing 404s that only appear in
 * production — build hrefs from BASE_URL instead.
 */

/** Join a site-relative path onto the configured base path. */
export function url(path: string): string {
  const base = import.meta.env.BASE_URL;
  const prefix = base.endsWith('/') ? base : `${base}/`;
  return prefix + path.replace(/^\/+/, '');
}

/**
 * URL-safe tag segment, NOT percent-encoded.
 *
 * This is the value handed to `getStaticPaths` as a route param, and Astro
 * encodes params itself when emitting paths — pre-encoding here would
 * double-encode and break the route match at build time. Spaces collapse to
 * hyphens so tags like "kv cache" do not produce a path with a literal space.
 */
export function tagSlug(tag: string): string {
  return tag.trim().toLowerCase().replace(/\s+/g, '-');
}

/** Href for a tag listing page (encoded, safe for an href attribute). */
export function tagUrl(tag: string): string {
  return url(`tags/${encodeURIComponent(tagSlug(tag))}`);
}

/** Href for a post detail page. */
export function postUrl(id: string): string {
  return url(`posts/${id}`);
}
