"use client";

import { avatarSrc } from "./avatar";
import { highlightFor } from "@/lib/contributors";
import { useCrowd } from "./use-crowd";
import { useDrift } from "./use-drift";
import { usePan } from "./use-pan";
import { countryName } from "@/lib/countries";
import { copy } from "@/lib/copy";
import type { CrowdPage, SignupRow } from "@/lib/db";

/**
 * The people, behind the headline.
 *
 * Everyone who has joined is on screen when the page opens, which does the
 * arguing a testimonial section would otherwise have to do.
 *
 * It used to scatter faces by hashing their seed. That read as a crowd at
 * twenty seven people and as a mess at a thousand, and it could only ever show
 * the handful that fitted the screen. It is a grid now, laid out column by
 * column, and it drifts sideways on its own. Hovering a face stops it, and it
 * can still be dragged.
 *
 * The middle of the hero is masked out rather than kept empty by placement.
 * That is what lets the grid be one continuous surface instead of two separate
 * gutters that would have to scroll in opposite directions to stay symmetric.
 */

/**
 * How many people the hero shows before it starts repeating them.
 *
 * This is a cost limit, not a design one. Every face is an image request, and
 * the drift pulls a new column into view roughly every two and a half seconds,
 * so a hero that walked the whole wall charged about two and a quarter requests
 * per second for as long as a tab stayed open. Ninety seconds of that was three
 * hundred requests from one reader, and it grew with the wall.
 *
 * Capping it makes the cost converge instead. The loop repeats the same faces,
 * the browser already has them, and once the first lap is done an idle tab costs
 * nothing at all. A hundred and eighty is thirty columns, so a lap takes about
 * eighty seconds. Everyone, genuinely everyone, is still on /wall.
 *
 * It has to divide by LOOP_ROWS.
 */
const HERO_CROWD = 180;

/**
 * How many faces are repeated after the last one so the loop has somewhere to
 * land. It only has to outrun the widest screen this will be read on, and it
 * cannot be longer than the run it repeats.
 */
const LOOP_LEAD = 240;

/**
 * And how many are repeated before the first one. Without these, the space to
 * the left of the opening face is empty at the top of the loop and full of
 * people everywhere else, which is the one part of the surface that would not
 * repeat. Two columns is more than the inset it replaces.
 */
const LOOP_TAIL = 12;

/**
 * Rows in the grid. Six on a wide screen and two on a narrow one, so a run
 * that divides by six divides by both.
 *
 * The run has to be a whole number of columns. Faces flow down a column before
 * moving to the next, so a run of 1832 in rows of six leaves the repeat
 * starting two rows down its column, and the whole crowd steps sideways and
 * down at the moment it wraps.
 */
const LOOP_ROWS = 6;

export function HeroBoard({ page, me }: { page: CrowdPage; me: SignupRow | null }) {
  const { people } = useCrowd(page, me);

  const surface = usePan<HTMLDivElement>();

  // The hero no longer asks for more people as it travels. One page from the
  // server is already more than it shows, so paging here only ever bought
  // faces that cost a request each and then scrolled away.
  const crowd = people.slice(0, HERO_CROWD);

  // The repeats need a run long enough to cover the screen, since the whole
  // point of the one after the end is to have somewhere to land.
  const looping = crowd.length >= HERO_CROWD;
  const run = looping ? crowd.slice(0, crowd.length - (crowd.length % LOOP_ROWS)) : crowd;
  const tail = looping ? run.slice(-LOOP_TAIL) : [];
  // Never longer than the run itself, which it now can be: the run used to be
  // the whole wall and is a few hundred people at most.
  const lead = looping ? run.slice(0, Math.min(LOOP_LEAD, run.length)) : [];
  const shown = [...tail, ...run, ...lead];

  useDrift(surface, shown.length);

  if (people.length === 0) return null;

  return (
    <div ref={surface} className="hero-board" aria-hidden>
      <div className={`hero-board__grid${looping ? " hero-board__grid--looping" : ""}`}>
        {shown.map((person, i) => {
          const isMe = me !== null && person.id === me.id;
          const highlight = highlightFor(person.id);
          return (
            <span
              key={
                i < tail.length
                  ? `${person.id}-before`
                  : i < tail.length + run.length
                    ? person.id
                    : `${person.id}-after`
              }
              className="hero-board__face"
              data-me={isMe || undefined}
              // The ring is the whole marking here. No pill: the hero keeps
              // names hidden until you point at one, and a caption riding on
              // every copy of a drifting face is the opposite of quiet.
              data-highlight={highlight ?? undefined}
              // The two ends of one run. The drift measures between them to
              // know how far it travels before it can start over.
              data-loop-from={i === tail.length || undefined}
              data-loop={i === tail.length + run.length || undefined}
              // Only the opening screenful is staggered, so it arrives as a
              // crowd rather than a block. Everyone after that appears at once:
              // faces from later pages mount while you are already dragging
              // towards them, and a delay there is just a blank space where a
              // person should be.
              style={i < 60 ? { animationDelay: `${i * 25}ms` } : undefined}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={avatarSrc(person.seed, person.gender)}
                alt=""
                width={64}
                height={64}
                // Only the faces that can be on screen before the first drag are
                // worth a request up front. The rest are one image each, and
                // there are hundreds of them.
                loading={i < 40 ? "eager" : "lazy"}
              />
              {isMe && <span className="hero-board__you">{copy.wall.you}</span>}
              <span className="hero-board__name">
                {person.name}
                <span className="hero-board__place">{countryName(person.country)}</span>
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
