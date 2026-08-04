"use client";

import { useState } from "react";
import Link from "next/link";

import { AvatarImage } from "./avatar";
import { PersonExperiences } from "./person-experiences";
import { usePeople } from "./people-provider";
import { useCrowd, useLoadOnApproach } from "./use-crowd";
import { usePan } from "./use-pan";
import { countryName } from "@/lib/countries";
import { copy } from "@/lib/copy";
import type { CrowdPage, SignupRow } from "@/lib/db";

/**
 * Everyone on the wall, and a way in for anyone not on it yet.
 *
 * Joining lives at /join now rather than in a form here, because it starts with
 * a redirect to Google and comes back to a second step; a form that vanishes
 * mid-flow and reappears somewhere else is worse than a link that says where it
 * goes.
 *
 * Each face is a button rather than a link: selecting someone opens their
 * interview experiences here instead of navigating away.
 */
export function Wall({ page, me }: { page: CrowdPage; me: SignupRow | null }) {
  const { joined } = usePeople();
  const [selected, setSelected] = useState<SignupRow | null>(null);
  const { people, total, loading, done, loadMore } = useCrowd(page, me);

  const surface = usePan<HTMLDivElement>();
  const onScroll = useLoadOnApproach(surface, "y", { done, loadMore, count: people.length });

  return (
    <>
      {/* scroll-mt-24 like every other anchor target. Lenis reads this value off
          the element to clear the fixed header, so an odd one out lands wrong. */}
      <section id="wall" className="scroll-mt-24 px-6 pt-28 md:px-12 lg:px-24">
        <div className="mx-auto w-full max-w-5xl">
          <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
            {copy.join.label}
          </p>
          <h1 className="mt-5 font-serif text-3xl leading-tight sm:text-4xl">
            {copy.join.heading}
          </h1>
          <p className="text-muted-foreground mt-4 text-base leading-relaxed">
            {copy.join.body}
          </p>

          {joined ? (
            <p className="mt-6 rounded-lg border p-4 text-sm font-medium">{copy.join.joined}</p>
          ) : (
            <>
              <Link href="/join" className="btn-solid mt-6 inline-flex">
                {copy.join.submit}
              </Link>
              <p className="text-muted-foreground mt-3 text-xs">{copy.join.why}</p>
            </>
          )}
        </div>
      </section>

      <section className="px-6 pt-24 pb-32 md:px-12 lg:px-24">
        <div className="mx-auto w-full max-w-5xl">
          <h2 className="text-muted-foreground mb-6 font-mono text-[11px] tracking-[0.2em] uppercase">
            {copy.wall.heading}
          </h2>

          {people.length === 0 ? (
            <p className="text-muted-foreground text-sm">{copy.wall.empty}</p>
          ) : (
            <>
              {/* The count is the whole wall. The faces below it are however
                  many have been fetched so far, which is a different number and
                  always will be once the wall outgrows one request. */}
              <p className="text-muted-foreground mb-6 text-sm">
                {copy.wall.caption(total)}{" "}
                <span className="text-muted-foreground/70">{copy.wall.tapHint}</span>
              </p>

              <div
                ref={surface}
                onScroll={onScroll}
                className="wall-canvas"
                tabIndex={0}
                role="group"
                aria-label={copy.wall.heading}
              >
                <ul
                  className="wall-grid"
                  style={{ "--cols": columnsFor(total) } as React.CSSProperties}
                >
                  {people.map((person) => {
                    const isMe = me !== null && person.id === me.id;
                    return (
                      <li key={person.id}>
                        <button
                          type="button"
                          onClick={() => setSelected(person)}
                          aria-label={copy.wall.personAria(person.name)}
                          className="wall-tile focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                          data-me={isMe || undefined}
                        >
                          <span className="wall-tile__face">
                            <AvatarImage seed={person.seed} gender={person.gender} />
                            {isMe && <span className="wall-tile__you">{copy.wall.you}</span>}
                          </span>
                          <span className="mt-2 w-full truncate text-xs font-medium">
                            {person.name}
                          </span>
                          <span className="text-muted-foreground w-full truncate text-[11px]">
                            {countryName(person.country)}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <p className="text-muted-foreground mt-3 text-xs">
                {loading ? copy.wall.loadingMore : copy.wall.dragHint}
              </p>
            </>
          )}
        </div>
      </section>

      <PersonExperiences person={selected} onClose={() => setSelected(null)} />
    </>
  );
}

/**
 * How wide the wall is, in faces.
 *
 * Roughly square, so a wall of a thousand runs off the screen in both
 * directions rather than being one very long column. Derived from the total
 * rather than from how many rows have loaded, so later pages extend the wall
 * downward instead of reflowing every face already on screen.
 */
function columnsFor(total: number): number {
  return Math.min(36, Math.max(8, Math.ceil(Math.sqrt(total * 1.4))));
}
