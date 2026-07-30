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
    /**
     * Backfilled retrospective: written after the fact about an
     * earlier event. Labelled in the UI so the reader knows this is
     * not same-day reporting.
     */
    retro: z.boolean().default(false),
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

/**
 * Classics: annotated, deconstructed editions of primary texts.
 *
 * The design constraint that shapes this schema: a reader who finishes the
 * piece should *understand, be able to use, and remember* the argument -- not
 * merely have read a translation. Three lessons from prior art drive it:
 *
 *  1. Arbital tried to build a prerequisite graph by hand and died of author
 *     burden. So prerequisites here are only *declared* per section (a list of
 *     concept slugs); the graph and the reading order are computed from those
 *     declarations, never hand-maintained.
 *  2. The Rust Book and Matuschak's mnemonic medium both show that recall
 *     needs questions embedded *in* the text, at the point of exposure, not a
 *     quiz bolted on at the end. Hence `checks` lives inside each section.
 *  3. Annotation only works when the note sits beside the sentence it explains
 *     (Tufte sidenotes), so notes are authored inline in the section body via
 *     the <Sidenote> component rather than collected in a footer.
 */
const classics = defineCollection({
  // .mdx as well as .md: deconstructions embed Sidenote/Check/Prereq
  // components inline, which plain markdown cannot express.
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/classics' }),
  schema: z.object({
    title: z.string().min(1),
    /** The original work's own title, as published. */
    originalTitle: z.string().min(1),
    author: z.string().min(1),
    /** Publication year of the original, for the header line. */
    // Coerced to string so frontmatter may write 2008 or "公元前 350 年".
    originalYear: z.coerce.string().min(1),
    description: z.string().min(1),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    field: z
      .enum(['crypto', 'philosophy', 'mathematics', 'physics', 'computing', 'economics', 'other'])
      .default('other'),
    tags: z.array(z.string()).default([]),
    /**
     * The primary text itself. Required: a deconstruction with no verifiable
     * original is just an essay, and the whole point is that a reader can
     * check us against the source.
     */
    primary: source,
    /** Checksum of the exact artifact we read, when it is a fixed file. */
    primaryChecksum: z.string().optional(),
    sources: z.array(source).default([]),
    /**
     * Concepts a reader needs *before* section 1. Slugs into the concepts
     * collection. The ideal this section is built toward: every entry here
     * resolves to a page on this site, so the prerequisites are never a
     * dead-end instruction to go read something else.
     */
    prerequisites: z.array(z.string()).default([]),
    /** Honest reading-level assessment, shown to the reader up front. */
    difficulty: z.object({
      /** Who can follow this as written, e.g. "高中数学基础". */
      audience: z.string().min(1),
      /** Minutes, for the whole piece. */
      minutes: z.number().int().positive(),
      /** What genuinely cannot be dumbed down further, stated plainly. */
      hardParts: z.array(z.string()).default([]),
    }),
    /**
     * Further reading, ordered easiest-first. This is the "book list" that
     * lets a motivated reader close a gap we cannot close inline.
     */
    reading: z
      .array(
        z.object({
          title: z.string().min(1),
          author: z.string().optional(),
          note: z.string().min(1),
          url: z.string().optional(),
          /** Rough entry point, so a beginner is not handed a graduate text. */
          level: z.enum(['intro', 'core', 'deep']).default('core'),
        }),
      )
      .default([]),
    take: z.string().optional(),
    generatedBy: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts, dreams, concepts, classics };
