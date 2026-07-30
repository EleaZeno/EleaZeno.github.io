/*
 * Does an entry carry margin notes?
 *
 * The reading layout reserves ~18.5rem on the right of the text column for
 * floated sidenotes. That reservation is only correct when notes actually
 * exist: on an entry without them it left an empty strip beside text squeezed
 * into --measure, which reads as prose crammed against the left edge.
 *
 * Detection is on the raw body rather than the rendered HTML because the
 * layout class has to be decided before <Content /> renders.
 */
export function hasSidenotes(body: string | undefined): boolean {
  if (!body) return false;
  // <Sidenote ...> in MDX, or a hand-written aside carrying the class in md.
  return /<Sidenote[\s>]/.test(body) || /class=["'][^"']*\bsidenote\b/.test(body);
}
