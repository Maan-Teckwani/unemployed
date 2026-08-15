import type { ApplicationRow, Status } from "@/lib/api";

/**
 * The shape and arithmetic of the pile. No DOM, no React — the geometry is
 * decided here so the component only has to draw it.
 *
 * The pile is every application you have sent, drawn as sheets of paper seen
 * edge-on. It measures effort, not outcomes: a job that was rejected keeps its
 * sheet, because being turned down does not un-send the application, and a
 * counter that falls on the day you get rejected is a counter that punishes the
 * moment least able to take it.
 */

/**
 * How far one application got. This is what colours its sheet.
 *
 * Coarser than the status list on purpose: "applied" and "outreach sent" are
 * the same thing to a pile — it went out and nothing has come back — and a pile
 * that distinguishes them is a pile with a colour nobody can read.
 */
export type State = "sent" | "test" | "interview" | "offer" | "rejected";

/** In funnel order, which is also the order the legend reads. */
export const STATES: { id: State; label: string; hint: string }[] = [
  { id: "sent", label: "Sent", hint: "Out the door, nothing back yet" },
  { id: "test", label: "Test", hint: "An assessment or take-home" },
  { id: "interview", label: "Interview", hint: "You are talking to them" },
  { id: "offer", label: "Offer", hint: "The point of all of this" },
  { id: "rejected", label: "Rejected", hint: "Stays in the pile. You still did the work" },
];

export function stateOf(status: Status): State {
  switch (status) {
    case "test":
      return "test";
    case "interview":
      return "interview";
    case "offer":
      return "offer";
    case "rejected":
      return "rejected";
    default:
      return "sent";
  }
}

/** A sheet in the pile — something you actually sent. */
export type Sheet = {
  jobId: number;
  title: string;
  company: string;
  appliedAt: Date;
  state: State;
};

export type StackModel = {
  /** Oldest first, so index 0 is the bottom of the pile. */
  sheets: Sheet[];
  total: number;
  today: number;
  target: number;
  /** How many sheets are in each state, for the legend. */
  byState: Record<State, number>;
  /** The next round number above `total`, or null once past the last one. */
  nextMilestone: number | null;
};

/** Statuses that mean the application went out. Mirrors backend SENT. */
const SENT: Status[] = [
  "applied",
  "outreach_sent",
  "test",
  "interview",
  "offer",
  "rejected",
];

export const MILESTONES = [25, 50, 100, 250, 500] as const;

/** How tall the pile is allowed to get, in pixels, before sheets compress. */
export const MAX_PILE_H = 208;

/**
 * The shortest the drawing is allowed to be.
 *
 * A pile of three is a short pile, and it should look like one — but the
 * container cannot collapse to three pixels, because the text beside it is
 * bottom-aligned to this and would end up floating. Enough room for the empty
 * state to sit in, and no more.
 */
export const MIN_PILE_H = 88;

/** Sheets drawn individually. Below this they fuse into slabs — see `slabs`. */
export const RENDER_INDIVIDUAL = 80;

/**
 * The thickest a single sheet is ever drawn.
 *
 * This used to be 6px, which quietly made the pile useless for the person who
 * needs it most. At five applications the drawing was five hairlines a shade
 * off the page colour — so a beginner, opening the app to see what they had
 * done, saw very nearly nothing, and the state colours riding on a 1.5px edge
 * were not readable at all. The metaphor only started paying for its space at
 * around fifty sheets, which is the point at which you no longer need
 * encouragement.
 *
 * Twelve makes a pile of five read as five countable sheets. It costs nothing
 * later: `layout` divides the available height by the count, so the sheets thin
 * out on their own as the pile fills and the ceiling stops binding at all past
 * about seventeen.
 */
export const SHEET_MAX = 12;

/** Below this two sheets stop resolving as two, whatever the count. */
export const SHEET_MIN = 1.5;

/** Sheets per stratum. Matches the smallest milestone so strata line up with marks. */
export const SLAB_SIZE = 25;

/**
 * The most strata to draw.
 *
 * Without this the node count grows with the pile again, just more slowly —
 * a thousand applications would be forty blocks, and the whole point of the
 * strata was to stop the drawing scaling with the count. Past this, strata
 * simply hold more sheets each, which is what compression means.
 */
export const MAX_SLABS = 12;

export const DEFAULT_TARGET = 5;

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/**
 * How the pile is divided up at a given count.
 *
 * Fixed spacing works to about fifty applications and then runs off the top of
 * the screen. Simply shrinking the gap does not solve it either: below roughly
 * a pixel and a half two sheets stop resolving as two, and at a few hundred
 * applications even that floor overflows.
 *
 * So the pile is drawn in two parts. The recent sheets keep a spacing you can
 * count, and everything older shares a fixed band at the bottom that gets
 * denser as the pile grows. The drawing therefore never exceeds MAX_PILE_H
 * however long the job hunt runs — which is also what a real stack of paper
 * does, since the bottom of one is compressed by everything above it.
 */
export type Layout = {
  /** Sheets old enough to be drawn as strata rather than individually. */
  compressed: number;
  /** Sheets drawn one by one, at the top. */
  shown: number;
  /** Gap between two individually drawn sheets, in px. */
  pitch: number;
  /** Height of the strata band at the bottom, in px. Zero until it is needed. */
  slabH: number;
  /** Total height of the drawing, in px. Never more than MAX_PILE_H. */
  height: number;
};

export function layout(count: number): Layout {
  const compressed = Math.max(0, count - RENDER_INDIVIDUAL);
  const shown = Math.min(count, RENDER_INDIVIDUAL);
  // With nothing compressed the sheets own the full height. Once there is a
  // band underneath, they give up the bottom 45% of it to the strata.
  const region = compressed > 0 ? MAX_PILE_H * 0.55 : MAX_PILE_H;
  const p = Math.min(SHEET_MAX, Math.max(SHEET_MIN, region / Math.max(shown, 1)));
  const slabH = compressed > 0 ? MAX_PILE_H - shown * p : 0;
  return { compressed, shown, pitch: p, slabH, height: shown * p + slabH };
}

/**
 * Where a sheet sits, measured up from the bottom of the pile.
 *
 * `index` is 0 for the oldest. Inside the strata the mapping is proportional,
 * which is what keeps a milestone tick pointing at the right stratum however
 * many hundreds are packed into it.
 */
export function sheetY(index: number, count: number): number {
  const { compressed, pitch, slabH } = layout(count);
  if (compressed > 0 && index < compressed) {
    return (index / compressed) * slabH;
  }
  return slabH + (index - compressed) * pitch;
}

/**
 * A small deterministic number in [0, 1) from a job id.
 *
 * Deterministic matters: a sheet's lean is part of how you recognise the pile,
 * and `Math.random()` would reshuffle every sheet on every render, so the pile
 * would look like a different pile each time the page loaded.
 */
function jitter(seed: number, salt: number): number {
  const x = Math.sin(seed * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Horizontal offset in px — how squarely this sheet was dropped. */
export function offsetX(jobId: number): number {
  return (jitter(jobId, 1) - 0.5) * 7;
}

/**
 * How much shorter this sheet is than the widest one, in px.
 *
 * Varying the width does most of the work of making a stack look like paper:
 * real sheets are the same size but never line up, so what you see from the
 * side is a ragged right edge. It reads far better than rotating each one,
 * which at these heights just looks like shredding.
 */
export function shorten(jobId: number): number {
  return jitter(jobId, 3) * 22;
}

/** Lean in degrees. Barely any: at three pixels tall, rotation reads as noise. */
export function rotation(jobId: number): number {
  return (jitter(jobId, 2) - 0.5) * 0.7;
}

/**
 * The sheets below the individually-drawn ones, grouped into blocks.
 *
 * Past a couple of hundred applications, drawing every sheet is thousands of
 * nodes for a texture nobody can resolve. Older sheets become strata instead —
 * one element per block, striped at the current pitch — which keeps the node
 * count flat however long the job hunt runs.
 */
export function slabs(
  count: number,
): { from: number; to: number; y: number; height: number; stripe: number }[] {
  const { compressed, slabH } = layout(count);
  if (compressed === 0) return [];

  const perSheet = slabH / compressed;
  const size = Math.max(SLAB_SIZE, Math.ceil(compressed / MAX_SLABS));
  const out = [];
  for (let from = 0; from < compressed; from += size) {
    const to = Math.min(from + size, compressed);
    out.push({
      from,
      to,
      y: from * perSheet,
      height: (to - from) * perSheet,
      // The hairline spacing inside a block. Below a pixel the stripes stop
      // rendering at all and the block reads as a solid slab, which is the
      // honest thing for a stratum holding hundreds of sheets anyway.
      stripe: Math.max(1, perSheet),
    });
  }
  return out;
}

export function nextMilestone(total: number): number | null {
  return MILESTONES.find((m) => m > total) ?? null;
}

/**
 * Turn the applications list into the pile.
 *
 * A sheet is anything with an `applied_at`, which the backend stamps once and
 * never moves — that, rather than the current status, is why a closed job keeps
 * its sheet. Ghosts are read from status, because a prepared resume is a state
 * you are currently in rather than something that happened.
 *
 * "Today" is bucketed here rather than on the server on purpose: the backend
 * and the browser are the same machine, but a server-side date still bakes in a
 * timezone assumption, and `toDateString()` is right by construction.
 */
export function buildStack(
  rows: ApplicationRow[],
  target = DEFAULT_TARGET,
  now = new Date(),
): StackModel {
  const sheets: Sheet[] = [];

  for (const row of rows) {
    const dated = row.applied_at ? new Date(row.applied_at) : null;
    const valid = dated && !Number.isNaN(dated.getTime());

    // A date is the real test — the backend stamps it once and never moves it,
    // which is why a rejected job keeps its sheet. Status is only the fallback
    // for a row written before the column existed.
    if (!valid && !SENT.includes(row.status)) continue;

    sheets.push({
      jobId: row.job_id,
      title: row.title,
      company: row.company,
      appliedAt: valid ? dated : new Date(0),
      state: stateOf(row.status),
    });
  }

  sheets.sort((a, b) => a.appliedAt.getTime() - b.appliedAt.getTime());

  const byState = { sent: 0, test: 0, interview: 0, offer: 0, rejected: 0 };
  for (const sheet of sheets) byState[sheet.state] += 1;

  return {
    sheets,
    total: sheets.length,
    today: sheets.filter((s) => isSameDay(s.appliedAt, now)).length,
    target,
    byState,
    nextMilestone: nextMilestone(sheets.length),
  };
}

/**
 * The line under the pile that makes the number mean something.
 *
 * Deliberately hedged. This app cannot measure anyone's reply rate, and the
 * rest of it is careful never to assert what it has not measured — so this says
 * "a rough rule" and means it, rather than dressing a guess up as your
 * statistics.
 */
export function framing(model: StackModel): string {
  const { total, today, target, byState } = model;

  if (total === 0) {
    return "Nothing in the pile yet. Open a role from Apply today, send it, then set its status to Applied — it lands here.";
  }
  if (byState.offer > 0) {
    return `${byState.offer} offer${byState.offer === 1 ? "" : "s"} out of ${total} sent. That is what the pile was for.`;
  }
  if (byState.interview > 0) {
    return `${byState.interview} at interview out of ${total} sent. The pile is doing its job.`;
  }
  if (total < 25) {
    return `As a rough rule, first replies start landing somewhere between 25 and 40 applications sent. You are at ${total}.`;
  }
  if (total < 40) {
    return `You are inside the range where first replies usually start — roughly 25 to 40 sent. Silence here is normal, not a verdict.`;
  }
  if (today >= target) {
    return `${total} sent. Today's ${target} are done.`;
  }
  return `${total} sent. Past the point where most people have heard something back — keep the daily number up.`;
}
