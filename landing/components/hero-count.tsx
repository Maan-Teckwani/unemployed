"use client";

import { usePeople } from "./people-provider";
import { copy } from "@/lib/copy";

/**
 * The headcount under the hero buttons, which ticks up the moment you join.
 *
 * The number is the whole wall, counted in the database, not the length of the
 * page of faces sent to the browser. Those were the same thing while the wall
 * was smaller than one request and have not been since.
 */
export function HeroCountLine({ total }: { total: number }) {
  const { added } = usePeople();
  const count = total + added.length;
  if (count === 0) return null;

  return (
    <p className="text-amber-500 mt-8 font-mono text-xs tracking-wider">
      {copy.hero.counting(count)}
    </p>
  );
}
