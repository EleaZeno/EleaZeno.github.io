/**
 * Wrap markdown tables in a horizontally scrollable container.
 *
 * Mono, multi-column tables (the probability tables in the Bitcoin
 * deconstruction are 11 rows x 2 cols of 7-decimal figures) are wider than a
 * phone column. An unwrapped table widens its block container, which pushes the
 * whole document sideways -- the reader then cannot scroll the page vertically
 * without drift. Scrolling the table alone keeps the page stable.
 *
 * tabindex="0" + role/aria-label make the scroll region reachable by keyboard,
 * which a bare overflow container is not.
 */
export default function rehypeTableScroll() {
  return (tree) => {
    visit(tree);
  };
}

function visit(parent) {
  const children = parent.children;
  if (!Array.isArray(children)) return;

  for (let i = 0; i < children.length; i += 1) {
    const node = children[i];
    if (node.type !== 'element') continue;

    if (node.tagName === 'table') {
      children[i] = {
        type: 'element',
        tagName: 'div',
        properties: {
          className: ['table-scroll'],
          tabindex: '0',
          role: 'region',
          'aria-label': '可横向滚动的表格',
        },
        children: [node],
      };
      continue;
    }

    visit(node);
  }
}
