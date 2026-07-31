import { visit } from 'unist-util-visit';

/**
 * Tag English-language blockquotes with `lang="en"`.
 *
 * The page is `<html lang="zh-CN">`, but in a deconstruction the quoted primary
 * text is English. Marking it matters for three separate consumers:
 *
 *  1. Pop-up dictionary extensions (沙拉查词, 欧路, Safari's long-press lookup)
 *     read the nearest `lang` to pick a source language. Left as zh-CN they try
 *     to look up English words in a Chinese dictionary and return nothing.
 *  2. Screen readers switch pronunciation engines on `lang`, so unmarked
 *     English is read out with Mandarin phonetics.
 *  3. Browsers apply language-specific line-breaking; CJK rules break English
 *     mid-word.
 *
 * Deliberately NOT done here: splitting words into per-word <span> elements.
 * That would let us attach a native dictionary, but it destroys text selection
 * -- extensions and the OS lookup both operate on the DOM selection, and a
 * selection spanning many spans comes back fragmented or empty. Keeping quote
 * text as unbroken text nodes is what makes every external dictionary work for
 * free, so it is a load-bearing constraint, not an omission. See also the
 * reader hint rendered by classics/[...id].astro.
 *
 * Heuristic: a quote is English when its text is majority ASCII letters and it
 * contains no CJK. Chinese pull-quotes in the same body are left alone.
 */
const CJK = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]/;

function textOf(node) {
  let out = '';
  visit(node, 'text', (t) => {
    out += t.value;
  });
  return out;
}

/**
 * Second job: mark the Chinese rendering that follows a quote.
 *
 * Every English quotation in a deconstruction is followed by its Chinese
 * translation as an ordinary paragraph. Styling that pairing (see `.zh` in
 * global.css) needs the paragraph identified, and doing it here rather than by
 * hand-authoring a class keeps the MDX plain Markdown -- authors just write the
 * translation under the quote and the pairing appears.
 *
 * A following paragraph counts as the translation when it is CJK and short
 * enough to be a rendering rather than the start of the analysis. The length
 * cap is what keeps a long commentary paragraph from being restyled.
 */
const MAX_TRANSLATION_CHARS = 420;

function isEnglishQuote(node) {
  if (node.tagName !== 'blockquote') return false;
  const text = textOf(node).trim();
  if (!text || CJK.test(text)) return false;
  const letters = text.replace(/[^A-Za-z]/g, '').length;
  // Guard against tagging a quote that is only digits or a formula.
  return letters >= 12 && letters / text.length >= 0.5;
}

export default function rehypeQuoteLang() {
  return (tree) => {
    visit(tree, 'element', (node) => {
      if (isEnglishQuote(node)) {
        node.properties = node.properties || {};
        if (!node.properties.lang) node.properties.lang = 'en';
      }
    });

    // Pair pass: needs sibling order, so it walks containers rather than nodes.
    // Not scoped to 'element' -- at the top level the siblings sit directly
    // under the `root` node, which is where every quote in a deconstruction
    // actually lives.
    visit(tree, (parent) => {
      if (!Array.isArray(parent.children)) return;
      parent.children.forEach((child, i) => {
        if (!isEnglishQuote(child)) return;

        // Skip whitespace-only text nodes between the two elements.
        let j = i + 1;
        while (j < parent.children.length) {
          const sib = parent.children[j];
          if (sib.type === 'text' && !sib.value.trim()) { j += 1; continue; }
          break;
        }
        const next = parent.children[j];
        if (!next || next.type !== 'element' || next.tagName !== 'p') return;

        const zh = textOf(next).trim();
        if (!zh || !CJK.test(zh) || zh.length > MAX_TRANSLATION_CHARS) return;

        next.properties = next.properties || {};
        const cls = next.properties.className;
        const list = Array.isArray(cls) ? cls : cls ? [cls] : [];
        if (!list.includes('zh')) next.properties.className = [...list, 'zh'];
      });
    });
  };
}
