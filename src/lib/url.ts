/**
 * Base-path-aware URL helpers.
 *
 * `new URL('/x', Astro.url)` resolves against the origin and silently drops a
 * project-site base path, producing links that 404 only in production. Build
 * every internal href from BASE_URL instead.
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
 * This value is handed to `getStaticPaths` as a route param and Astro encodes
 * params itself; pre-encoding here would double-encode and break the build-time
 * route match. Spaces collapse to hyphens so "kv cache" never yields a path
 * containing a literal space.
 */
export function tagSlug(tag: string): string {
  return tag.trim().toLowerCase().replace(/\s+/g, '-');
}

/** Href for a tag listing (encoded, safe to put in an attribute). */
export function tagUrl(tag: string): string {
  return url(`tags/${encodeURIComponent(tagSlug(tag))}`);
}

export function postUrl(id: string): string {
  return url(`posts/${id}`);
}

/** Bare hostname, for showing provenance next to a citation. */
export function hostOf(link: string): string {
  try {
    return new URL(link).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/** Href for a domain index page. */
export function domainUrl(domain: string): string {
  return url(`domains/${domain}`);
}
