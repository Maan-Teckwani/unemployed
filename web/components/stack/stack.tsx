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

const SHEET_W = 200;
/** Space to the right of the sheets for the milestone ticks. */
const GUTTER = 46;

/** One class per state, so the pile, the legend and the tooltips cannot drift. */
const EDGE: Record<State, string> = {
  sent: "border-state-sent",
  test: "border-state-test",
  interview: "border-state-interview",
  offer: "border-state-offer",
  rejected: "border-state-rejected",
};
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
 * on what you expected. So the pile carries four things instead: what you can
 * still do today, how much is behind you, how far each one got, and an honest
 * sentence about what the total means. The drawing is the part that makes it
 * feel like something, because a stack of paper getting thicker is already how
 * people picture effort.
 *
 * Nothing here is only visual. Every count is in text beneath it, every state
 * is named in the legend, and colour is never the only thing carrying a fact.
 */
export function Stack() {
  const { model, landed } = useStack();
  const { total, today, target, nextMilestone, byState } = model;

  return (
    <section aria-labelledby="stack-heading" className="space-y-5">
      <h2 id="stack-heading" className="sr-only">
        Your application pile
      </h2>

      <div className="flex flex-wrap items-center gap-x-10 gap-y-6">
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

          <p className="max-w-prose text-sm text-muted-foreground">{framing(model)}</p>
        </div>
      </div>

      <Legend byState={byState} total={total} />

      {/* What the thing is for. Without this the pile is decoration, and the
          one action that makes it grow is buried in a dropdown on another page. */}
      <p className="max-w-prose text-xs text-muted-foreground">
        {total === 0 ? (
          <>
            Every application you send adds a sheet. Send one from{" "}
            <Link href="/today" className="underline underline-offset-4">
              Apply today
            </Link>
            , then set its status to <strong className="font-medium">Applied</strong> —
            it lands here. As you hear back, move it to Test, Interview or Offer and
            its sheet changes colour.
          </>
        ) : (
          <>
            Set a job&apos;s status as you hear back — Test, Interview, Offer — and its
            sheet changes colour. Being rejected does not remove a sheet: you still
            sent it. Marked one by mistake? Put it back to{" "}
            <strong className="font-medium">To do</strong> and its sheet leaves.
          </>
        )}
      </p>

      {total === 0 && (
        <Link href="/today" className={buttonVariants({ variant: "default", size: "sm" })}>
          Find something to apply to →
        </Link>
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

/** What the colours mean, and how many are in each. */
function Legend({
  byState,
  total,
}: {
  byState: Record<State, number>;
  total: number;
}) {
  if (total === 0) {
    return (
      <ul className="flex flex-wrap gap-x-5 gap-y-2">
        {STATES.map((s) => (
          <li key={s.id} className="flex items-center gap-1.5" title={s.hint}>
            <span className={`h-2.5 w-4 rounded-[1px] ${FILL[s.id]} opacity-40`} aria-hidden />
            <span className="meta">{s.label}</span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2">
      {STATES.map((s) => {
        const n = byState[s.id];
        return (
          <li
            key={s.id}
            title={s.hint}
            className={`flex items-center gap-1.5 ${n === 0 ? "opacity-45" : ""}`}
          >
            <span className={`h-2.5 w-4 rounded-[1px] ${FILL[s.id]}`} aria-hidden />
            <span className="data text-data text-foreground">{n}</span>
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
          A stack seen from the side is not a row of boxes — it is the *edges*
          of pages: a pale sliver with a darker line under it, each a little
          shorter or further left than the last. So there is no box here, only a
          bottom edge, and the state colours that edge rather than filling the
          page. Colour then reads as an annotation on a pile of paper instead of
          turning the whole thing into a bar chart. */}
      <ul>
        {individual.map((sheet, i) => {
          const index = geo.compressed + i;
          const newest = index === total - 1;
          const coloured = sheet.state !== "sent";
          const named = Boolean(sheet.company);
          const label = named
            ? `${sheet.title} at ${sheet.company} — ${STATE_LABEL[sheet.state]}`
            : "A sent application";
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
                className={`absolute inset-x-0 bottom-0 bg-paper transition-[filter] group-hover/sheet:brightness-95 dark:group-hover/sheet:brightness-125 ${
                  coloured
                    ? `${EDGE[sheet.state]} border-b-[1.5px]`
                    : "border-b border-paper-edge"
                }`}
                style={{
                  height: Math.max(2, geo.pitch - 0.5),
                  // A hint of the state through the page itself, so a coloured
                  // sheet still reads at a glance when the pile is dense.
                  backgroundColor: coloured
                    ? `color-mix(in oklch, var(--color-state-${sheet.state}) 12%, var(--paper))`
                    : undefined,
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
