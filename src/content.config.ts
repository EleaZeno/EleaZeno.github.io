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
    /**
     * Published errata. Append-only: a wrong claim is never silently
     * edited out of the body, because the trail of having been wrong is
     * itself the evidence that these gates work. Rendered at the top of
     * the post so a reader cannot consume the error without the fix.
     */
    corrections: z
      .array(
        z.object({
          date: z.coerce.date(),
          /** Verbatim quote of what the post originally claimed. */
          was: z.string().min(1),
          /** What the evidence actually supports. */
          now: z.string().min(1),
          /** How the error was caught, so the mechanism is auditable. */
          why: z.string().optional(),
        }),
      )
      .default([]),
    /** Rotation bookkeeping. */
    topic: z.string().optional(),
    generatedBy: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

/**
 * Nightly reflections: one entry per night, not per cycle.
 *
 * Earlier this collection stored one file per REM-style cycle and the index
 * page rendered every one of them in full, so a night arrived as three
 * untitled walls of text with no way to link to a single night. A night is
 * now a titled piece with its own page, and the cycles inside it are `##`
 * sections of one argument. Nights that produced nothing worth reading are
 * simply not written — there is no quota to fill.
 */
const dreams = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/dreams' }),
  schema: z.object({
    date: z.coerce.date(),
    /** Headline for the night. Same contract as a post title: name the finding. */
    title: z.string().min(4).max(46),
    /** One or two sentences shown in listings and in the RSS feed. */
    summary: z.string().min(10).max(200),
    /**
     * How many reflection cycles the night was assembled from. Provenance
     * only: it is shown as a stamp, never used for ordering or routing.
     */
    cycles: z.number().int().min(1).default(1),
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
  // .mdx too: a concept that carries <Sidenote> must be MDX, otherwise the tag
  // passes through as inert raw HTML and its markdown links stay literal.
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/concepts' }),
  schema: z.object({
    title: z.string().min(1),
    /** Other spellings that should also auto-link here (EN/CN, abbreviations). */
    aliases: z.array(z.string()).default([]),
    /** One plain sentence, no jargon. Shown on hover and in the glossary. */
    oneLiner: z.string().min(1),
    domain: z
      .enum([
        'ai',
        'crypto',
        'physics',
        'bio',
        'space',
        'energy',
        'compute',
        'systems',
        'theory',
        // Learning science: the education classics need a home, and the
        // reading-method pages they generate are load-bearing for this site's
        // own pedagogy rather than incidental subject matter.
        'learning',
        'other',
      ])
      .default('ai'),
    /** Rough difficulty, so the glossary can offer an easy path in. */
    level: z.enum(['intro', 'core', 'deep']).default('core'),
    /**
     * Concepts one level *below* this one: what you must already hold to
     * follow this page. Distinct from `related`, which is sideways -- a
     * neighbour at roughly equal depth.
     *
     * Splitting the two is what lets the build compute a reading order. A
     * flat undirected `related` list cannot answer "where do I start?",
     * because it has no direction; a reader landing on a `deep` page sees
     * ten neighbours and no floor. `prerequisites` is a DAG edge pointing
     * downward, so a topological walk from any page yields a path in.
     *
     * Same author-burden rule as classics: you declare one array per page
     * and the graph is derived. Never hand-maintain the reverse edges.
     */
    prerequisites: z.array(z.string()).default([]),
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
    /**
     * What the checksum was actually computed over.
     *
     * The canonical URL and the file actually fetched are not always the same
     * host (mirrors, CDNs, blocked networks). Stating the provenance keeps the
     * checksum honest: it proves which bytes were read, not that the canonical
     * host serves those bytes.
     */
    primaryChecksumNote: z.string().optional(),
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
     *
     * `relation` is what keeps this from becoming a pile of links: it states
     * *why* an item is here, so the build can group the list without the
     * author writing subheadings. It also makes an omission visible -- an
     * empty `counter` bucket renders as a standing reminder that we have not
     * yet found the material that argues against this text, which is the
     * bucket a reader most needs and an author most easily skips.
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
          /**
           * How this item stands to the primary text:
           *  - upstream:   cited by, or a direct input to, the original
           *  - parallel:   answers the same question a different way
           *  - downstream: what the idea became afterwards
           *  - counter:    disputes or limits the original's claims
           */
          relation: z
            .enum(['upstream', 'parallel', 'downstream', 'counter'])
            .default('parallel'),
          /** Concept slugs on this site, so the list points inward too. */
          concepts: z.array(z.string()).default([]),
        }),
      )
      .default([]),
    take: z.string().optional(),
    generatedBy: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts, dreams, concepts, classics };
