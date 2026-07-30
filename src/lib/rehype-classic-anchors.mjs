/**
 * Stable, citable anchors for annotated classics.
 *
 * Every section heading gets a permanent id of the form s<N>, and the page
 * renders a click-to-copy deep link. Reason: annotations, prerequisites and
 * cross-references all need to hang off a stable address. Retrofitting an
 * addressing scheme after content exists is painful, so it goes in first.
 *
 * Ids come from the section ORDER, not the heading text, so rewording a
 * Chinese heading does not break inbound links.
 */
export default function rehypeClassicAnchors() {
  return (tree, file) => {
    const path = String(file?.history?.[0] ?? '');
    if (!path.includes('/content/classics/')) return;

    let n = 0;
    for (const node of tree.children ?? []) {
      if (node.type !== 'element' || node.tagName !== 'h2') continue;
      n += 1;
      node.properties = node.properties ?? {};
      const id = 's' + n;
      node.properties.id = id;
      node.properties['data-anchor'] = id;
    }
  };
}
