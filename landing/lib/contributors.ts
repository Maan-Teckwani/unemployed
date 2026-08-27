/**
 * The people who built this, and how they are marked on the wall.
 *
 * A list of ids in code rather than a column on `signups`, because the list
 * changes when somebody sends a pull request, which is a code change already.
 * A column would need a migration and some way to set it, and nothing would
 * ever build the screen that sets it. Move this into the table on the day the
 * list is long enough to be a chore.
 *
 * Ids are strings because the driver hands bigints back as strings. Anything
 * comparing against them has to do the same, so `highlightFor` normalises.
 */

/** Whose project this is. One person, drawn a little brighter than the rest. */
export const MAKER_ID = "113";

/** Everyone who has contributed to it since. */
export const CONTRIBUTOR_IDS: readonly string[] = ["2676"];

/**
 * Pinned to the front of every wall, in this order, for every visitor.
 *
 * The wall is newest first, so without this the maker sits thousands of faces
 * deep and a contributor who joined last week sits just behind them. Neither is
 * findable, which makes marking them pointless.
 */
export const PINNED_IDS: readonly string[] = [MAKER_ID, ...CONTRIBUTOR_IDS];

export type Highlight = "maker" | "contributor" | "supporter";

/**
 * What ring this person gets, or null for everyone else.
 *
 * Three tiers now, and only two of them are in this file. Buying a coffee earns
 * the third, and that list cannot live in code the way the other two do: it
 * changes when somebody presses a button, not when somebody sends a pull
 * request, so it comes from the database and is passed in.
 *
 * Ranked rather than combined. Someone can be all three at once and a face can
 * only wear one ring, so the strongest claim wins and the pill under it says
 * the most interesting true thing about them.
 */
export function highlightFor(
  id: string | number,
  supporters: readonly string[] = [],
): Highlight | null {
  const key = String(id);
  if (key === MAKER_ID) return "maker";
  if (CONTRIBUTOR_IDS.includes(key)) return "contributor";
  return supporters.includes(key) ? "supporter" : null;
}
