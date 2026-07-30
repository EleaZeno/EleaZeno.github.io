/**
 * Reads concept frontmatter straight off disk for the build pipeline.
 *
 * The autolinker runs as a rehype plugin, which is configured before Astro's
 * content collections are queryable — so terms come from the filesystem here
 * rather than from getCollection().
 */
import { readdirSync, readFileSync } from 'node:fs';

const DIR = new URL('../content/concepts/', import.meta.url);

/** Minimal frontmatter reader: only the scalar/array fields we need. */
function readFrontmatter(text) {
  if (!text.startsWith('---')) return {};
  const end = text.indexOf('\n---', 3);
  if (end === -1) return {};
  const head = text.slice(3, end);
  const out = {};
  for (const line of head.split('\n')) {
    const m = /^([A-Za-z_]+):\s*(.*)$/.exec(line);
    if (!m) continue;
    const [, key, raw] = m;
    let v = raw.trim();
    if (v.startsWith('[') && v.endsWith(']')) {
      out[key] = v
        .slice(1, -1)
        .split(',')
        .map((s) => s.trim().replace(/^["']|["']$/g, ''))
        .filter(Boolean);
    } else {
      out[key] = v.replace(/^["']|["']$/g, '');
    }
  }
  return out;
}

/** [{ id, text, hint }] for every concept title and alias. */
export function loadTerms() {
  let files = [];
  try {
    files = readdirSync(DIR).filter((f) => f.endsWith('.md'));
  } catch {
    return [];
  }
  const terms = [];
  for (const file of files) {
    const id = file.replace(/\.md$/, '');
    const fm = readFrontmatter(readFileSync(new URL(file, DIR), 'utf8'));
    if (!fm.title) continue;
    const hint = fm.oneLiner ?? '';
    const surfaces = [fm.title, ...(fm.aliases ?? [])];
    for (const s of surfaces) {
      const text = String(s).trim();
      if (text.length >= 2) terms.push({ id, text, hint });
    }
  }
  return terms;
}
