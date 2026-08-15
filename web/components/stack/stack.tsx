"use client";

import Link from "next/link";
import { useRef } from "react";
import { gsap, OK, useGSAP } from "@/lib/motion";
import {
  framing,
  layout,
  MAX_PILE_H,
  MILESTONES,
  MIN_PILE_H,
  offsetX,
  rotation,
  sheetY,
  shorten,
  slabs,
  STATES,
  type StackModel,
  type State,
} from "@/lib/stack";
import { Odometer } from "@/components/stack/odometer";
import { useStack } from "@/components/stack/stack-provider";
import { buttonVariants } from "@/components/ui/button";

const SHEET_W = 176;
/** Space to the right of the sheets, for milestone ticks and state labels. */
const GUTTER = 74;

/**
 * How small the pile has to be before each sheet is worth naming individually.
 * Past this the labels stop being annotation and become a second list.
 */
const LABEL_LIMIT = 10;

/** One class per state, so the pile, the summary and the tooltips cannot drift. */
const FILL: Record<State, string> = {
  sent: "bg-state-sent",
  test: "bg-state-test",
  interview: "bg-state-interview",
  offer: "bg-state-offer",
  rejected: "bg-state-rejected",
};
const STATE_LABEL = Object.fromEntries(
  STATES.map((s) => [s.id, s.label]),
) as Record<State, string>;

/**
 * Everything you have sent, drawn as a pile of paper.
 *
 * A bare number says nothing — 23 is either a lot or nothing at all depending
 * on what you expected. So the pile carries three things instead: what you can
 * still do today, how much is behind you, and how far each one got. The drawing
 * is the part that makes it feel like something, because a stack of paper
 * getting thicker is already how people picture effort.
 *
 * Nothing here is only visual. Every count is in text beside it, every state is
 * named in the summary, and colour is never the only thing carrying a fact.
 */
export function Stack() {
  const { model, landed } = useStack();
  const { total, today, target, nextMilestone, byState } = model;

  return (
    <section aria-labelledby="stack-heading" className="space-y-5">
      <h2 id="stack-heading" className="sr-only">
        Your application pile
      </h2>

      <div className="flex flex-wrap items-end gap-x-10 gap-y-6">
        <Pile model={model} landed={landed} />

        <div className="min-w-0 flex-1 space-y-3 pb-1">
          {/* Today is the primary number, because it is the only one you can
              still change. The total is history; this is the ask. */}
          <div>
            <p className="flex items-baseline gap-2">
              <span className="font-serif text-display-xl text-foreground">{today}</span>
              <span className="data text-data-lg text-muted-foreground">
                of {target} today
              </span>
            </p>
            <Slots done={today} target={target} />
          </div>

          <p className="data text-data text-muted-foreground">
            <Odometer value={total} className="text-foreground" /> in the pile
            {nextMilestone && ` · ${nextMilestone - total} to ${nextMilestone}`}
          </p>

          <Summary byState={byState} total={total} />
        </div>
      </div>

      {total === 0 ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Link
            href="/today"
            className={buttonVariants({ variant: "default", size: "sm" })}
          >
            Find something to apply to →
          </Link>
          <p className="text-xs text-muted-foreground">
            Set a job to <strong className="font-medium">Applied</strong> and its
            sheet lands here.
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{framing(model)}</p>
      )}
    </section>
  );
}

/** Today's target, as things to fill in. */
function Slots({ done, target }: { done: number; target: number }) {
  const shown = Math.max(target, done);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1" aria-hidden>
      {Array.from({ length: Math.min(shown, 12) }, (_, i) => (
        <span
          key={i}
          className={`h-1 w-6 rounded-full transition-colors ${
            i < done ? "bg-foreground" : "bg-muted"
          }`}
        />
      ))}
      {shown > 12 && <span className="meta ml-1">+{shown - 12}</span>}
    </div>
  );
}

/**
 * The funnel, in one line.
 *
 * This replaced a five-item legend plus a paragraph explaining what the colours
 * meant. The counts were always the useful part; the paragraph was a manual
 * pinned to the screen you open every morning, and the tooltips say the same
 * thing at the moment you actually wonder.
 */
function Summary({
  byState,
  total,
}: {
  byState: Record<State, number>;
  total: number;
}) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {STATES.map((s) => {
        const n = byState[s.id];
        return (
          <li
            key={s.id}
            title={s.hint}
            className={`flex items-center gap-1.5 ${
              total > 0 && n === 0 ? "opacity-40" : ""
            }`}
          >
            <span
              className={`h-2.5 w-3 rounded-[1px] ${FILL[s.id]} ${
                total === 0 ? "opacity-40" : ""
              }`}
              aria-hidden
            />
            {total > 0 && (
              <span className="data text-data text-foreground">{n}</span>
            )}
            <span className="meta">{s.label}</span>
          </li>
        );
      })}
    </ul>
  );
}

function Pile({ model, landed }: { model: StackModel; landed: number }) {
  const { sheets, total, nextMilestone } = model;
  const scope = useRef<HTMLDivElement>(null);
  const geo = layout(total);
  const individual = sheets.slice(geo.compressed);

  // Settle the newest sheet when a thrown card arrives. Only the top one moves:
  // the pile is not rebuilding, it is receiving.
  useGSAP(
    () => {
      if (landed === 0) return;
      const mm = gsap.matchMedia();
      mm.add(OK, () => {
        gsap.from("[data-newest]", {
          y: -16,
          opacity: 0,
          duration: 0.34,
          ease: "power3.out",
        });
      });
      return () => mm.revert();
    },
    { scope, dependencies: [landed] },
  );

  const height = Math.max(MIN_PILE_H, Math.min(geo.height + 12, MAX_PILE_H + 12));

  const marks = MILESTONES.filter(
    (m) =>
      m <= total ||
      (m === nextMilestone && total > 0 && sheetY(m - 1, total) < height - 8),
  );

  // Naming each sheet only works while there is room to write beside it. Above
  // that the gutter belongs to the milestone ticks, which is also the point
  // where the pile is big enough to speak for itself.
  const nameSheets = total > 0 && total <= LABEL_LIMIT && marks.length === 0;

  return (
    <div
      ref={scope}
      role="group"
      aria-label={
        total === 0
          ? "Your pile is empty. Nothing sent yet."
          : `A pile of ${total} sent application${total === 1 ? "" : "s"}.`
      }
      className="relative shrink-0"
      style={{ width: SHEET_W + GUTTER, height, contain: "layout paint" }}
    >
      {total === 0 && (
        <div
          aria-hidden
          className="absolute bottom-0 left-0 rounded-[3px] border border-dashed border-paper-edge/70"
          style={{ width: SHEET_W, height: 14 }}
        />
      )}

      {/* Older sheets, fused into strata. One element per block however many
          hundreds are underneath, so the drawing never scales with the count. */}
      {slabs(total).map((slab) => (
        <div
          key={slab.from}
          aria-hidden
          title={`${slab.to - slab.from} older applications`}
          className="absolute left-0 rounded-[2px] border-x border-b border-paper-edge/50"
          style={{
            bottom: slab.y,
            height: slab.height,
            width: SHEET_W,
            backgroundImage: `repeating-linear-gradient(to top, var(--paper-edge) 0 1px, var(--paper) 1px ${slab.stripe}px)`,
          }}
        />
      ))}

      {/* The recent ones, one sheet each.
          A stack seen from the side is the *edges* of pages: a pale face with a
          darker line under it, each a little shorter or further left than the
          last. The state colours the whole face rather than a hairline on its
          underside — at the thickness a small pile is drawn at, an edge tint was
          a colour nobody could see, which made the funnel invisible exactly when
          it was small enough to matter. */}
      <ul>
        {individual.map((sheet, i) => {
          const index = geo.compressed + i;
          const newest = index === total - 1;
          const coloured = sheet.state !== "sent";
          const named = Boolean(sheet.company);
          const label = named
            ? `${sheet.title} at ${sheet.company} — ${STATE_LABEL[sheet.state]}`
            : "A sent application";
          const face = Math.max(2, geo.pitch - 1);
          return (
            // Each sheet owns exactly one horizontal band, edge to edge, and
            // the link fills it. Bands must not overlap: an earlier attempt
            // gave every link a few pixels of extra reach, and since the sheets
            // stack in document order the topmost one silently swallowed the
            // clicks meant for the two beneath it — most of the pile looked
            // clickable and was not.
            <li
              key={sheet.jobId}
              data-newest={newest ? "" : undefined}
              className="group/sheet absolute"
              style={{
                bottom: sheetY(index, total),
                height: geo.pitch,
                width: SHEET_W - shorten(sheet.jobId),
                left: Math.max(0, offsetX(sheet.jobId) + 5),
                transform: `rotate(${rotation(sheet.jobId)}deg)`,
              }}
            >
              <span
                aria-hidden
                className="absolute inset-x-0 bottom-0 rounded-[1.5px] bg-paper transition-[filter] group-hover/sheet:brightness-95 dark:group-hover/sheet:brightness-125"
                // `--state-*`, not `--color-state-*`. The theme block is
                // `@theme inline`, which folds those into the generated utility
                // classes and never emits them as custom properties — so
                // `var(--color-state-test)` resolves to nothing here, the
                // color-mix around it is invalid, and the declaration is
                // dropped. That is why coloured sheets used to draw as plain
                // paper. Utility classes like `bg-state-test` are unaffected.
                style={{
                  height: face,
                  backgroundColor: coloured
                    ? `color-mix(in oklch, var(--state-${sheet.state}) 42%, var(--paper))`
                    : undefined,
                  // The underside shadow of the sheet resting on top of this
                  // one. Without it the pile reads as ruled lines rather than
                  // as paper, because a flat face and a hairline is also what a
                  // table border looks like. Composited over the face so a
                  // coloured sheet keeps its state colour.
                  backgroundImage:
                    "linear-gradient(to bottom, transparent 55%, color-mix(in oklch, var(--foreground) 7%, transparent) 100%)",
                  borderBottom: `1px solid ${
                    coloured ? `var(--state-${sheet.state})` : "var(--paper-edge)"
                  }`,
                }}
              />
              <Link
                href={`/jobs/${sheet.jobId}`}
                title={
                  named
                    ? `${sheet.company} · ${sheet.title} — ${STATE_LABEL[sheet.state]}`
                    : "Just sent"
                }
                aria-label={label}
                className="absolute inset-0 focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
              />
            </li>
          );
        })}
      </ul>

      {/* The pile sits on something. Without this it floats. */}
      <div
        aria-hidden
        className="absolute -bottom-1 left-1 rounded-full bg-foreground/10 blur-[3px]"
        style={{ width: SHEET_W - 4, height: 3 }}
      />

      {/* What each sheet is, while there are few enough to say. This is what
          turns the drawing from a texture into something you can read: the one
          sheet that reached an interview is named, in place, next to itself. */}
      {nameSheets &&
        individual.map((sheet, i) => {
          const index = geo.compressed + i;
          const newest = index === total - 1;
          if (sheet.state === "sent" && !newest) return null;
          return (
            <div
              key={sheet.jobId}
              aria-hidden
              className="absolute flex items-center gap-1.5"
              style={{ bottom: sheetY(index, total) - 3, left: SHEET_W + 4 }}
            >
              <span
                className={`h-px w-2 ${
                  sheet.state === "sent" ? "bg-milestone/50" : FILL[sheet.state]
                }`}
              />
              <span
                className={`meta whitespace-nowrap ${
                  sheet.state === "sent" ? "text-muted-foreground/70" : ""
                }`}
              >
                {newest && sheet.state === "sent"
                  ? "newest"
                  : STATE_LABEL[sheet.state]}
              </span>
            </div>
          );
        })}

      {/* Where the pile is, and where it is going. Ticks rather than a bar:
          a bar turns "how much have I done" into "how far behind am I". */}
      {marks.map((m) => {
        const reached = m <= total;
        return (
          <div
            key={m}
            aria-hidden
            className="absolute flex items-center gap-1"
            style={{ bottom: Math.max(0, sheetY(m - 1, total)), left: SHEET_W + 6 }}
          >
            <span
              className={`h-px w-2.5 ${
                reached ? "bg-milestone" : "border-t border-dashed border-milestone/60"
              }`}
            />
            <span
              className={`data text-data-sm ${
                reached ? "text-muted-foreground" : "text-muted-foreground/60"
              }`}
            >
              {m}
            </span>
          </div>
        );
      })}
    </div>
  );
}
