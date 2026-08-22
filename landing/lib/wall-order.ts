import type { SignupRow } from "./db";

/**
 * The order every wall is drawn in.
 *
 * You first, because finding yourself is the reward for joining. Then the
 * people who built this, so they are beside you rather than somewhere in the
 * thousands. Then anyone who joined while you were looking, then the wall
 * itself, newest first.
 *
 * Pinning is a move and not a copy: an id is in `seen` from the moment it is
 * placed, so a pinned person appears once, at the front, however deep into the
 * wall their real row sits. That also covers the case where you are one of
 * them, which is otherwise two rings on one face and a duplicate underneath.
 *
 * A pure function rather than something inside the hook so the rule can be
 * checked without a browser. It is also the only place the order is decided,
 * which is what stops the hero and the wall page from disagreeing.
 */
export function orderWall({
  me,
  pinned = [],
  added = [],
  rows,
}: {
  me: SignupRow | null;
  pinned?: readonly SignupRow[];
  added?: readonly SignupRow[];
  rows: readonly SignupRow[];
}): SignupRow[] {
  const seen = new Set<string>();
  const out: SignupRow[] = [];
  for (const row of [...(me ? [me] : []), ...pinned, ...added, ...rows]) {
    if (seen.has(row.id)) continue;
    seen.add(row.id);
    out.push(row);
  }
  return out;
}
