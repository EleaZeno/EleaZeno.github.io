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
    domain: z.enum(['ai', 'crypto', 'systems', 'theory', 'other']).default('ai'),
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

export const collections = { posts, dreams };
