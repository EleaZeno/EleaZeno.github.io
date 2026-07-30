import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

/** A cited source. `title` is required so a bare URL never appears as a citation. */
const source = z.object({
  title: z.string().min(1),
  url: z
    .string()
    .refine((v) => /^https?:\/\//.test(v), { message: 'source url must be absolute http(s)' }),
  /** Optional publisher/venue, e.g. "arXiv", "Cloudflare Blog". */
  outlet: z.string().optional(),
});

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string().min(1),
    description: z.string().min(1),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    /** Editorial section. Drives the index grouping. */
    domain: z.enum(['ai', 'crypto', 'physics', 'bio', 'space', 'energy', 'compute', 'systems', 'theory', 'other']).default('ai'),
    /** Sources actually consulted while writing. Empty = unsourced explainer. */
    sources: z.array(source).default([]),
    /**
     * My own commentary, kept out of the body so it renders in a visually
     * distinct block and can never be confused with the explainer itself.
     */
    take: z.string().optional(),
    /** How much to trust the piece: settled fact vs. moving target. */
    confidence: z.enum(['high', 'medium', 'exploratory']).default('medium'),
    /** Rotation bookkeeping. */
    topic: z.string().optional(),
    generatedBy: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

/** Nightly reflections. Short, dated, lower-stakes than a post. */
const dreams = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/dreams' }),
  schema: z.object({
    date: z.coerce.date(),
    /** REM-cycle style index within one night. */
    cycle: z.number().int().min(1).default(1),
    seed: z.string().optional(),
    generatedBy: z.string().optional(),
  }),
});

/**
 * Concept pages: the wiki layer.
 *
 * Every technical term an article leans on gets one page here, written so a
 * non-specialist can follow it. Articles then link to the definition instead
 * of re-explaining it, which is what makes the terms compound over time.
 */
const concepts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/concepts' }),
  schema: z.object({
    title: z.string().min(1),
    /** Other spellings that should also auto-link here (EN/CN, abbreviations). */
    aliases: z.array(z.string()).default([]),
    /** One plain sentence, no jargon. Shown on hover and in the glossary. */
    oneLiner: z.string().min(1),
    domain: z
      .enum(['ai', 'crypto', 'physics', 'bio', 'space', 'energy', 'compute', 'systems', 'theory', 'other'])
      .default('ai'),
    /** Rough difficulty, so the glossary can offer an easy path in. */
    level: z.enum(['intro', 'core', 'deep']).default('core'),
    related: z.array(z.string()).default([]),
    sources: z.array(source).default([]),
    updatedDate: z.coerce.date().optional(),
  }),
});

export const collections = { posts, dreams, concepts };
