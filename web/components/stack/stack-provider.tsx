"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, type SetupStatus, type Status } from "@/lib/api";
import { DUR, EASE, gsap } from "@/lib/motion";
import {
  buildStack,
  DEFAULT_TARGET,
  nextMilestone,
  offsetX,
  rotation,
  type Sheet,
  type StackModel,
  type State,
  stateOf,
} from "@/lib/stack";

/** Recount the legend after the pile changes. */
function countStates(sheets: Sheet[]): Record<State, number> {
  const out = { sent: 0, test: 0, interview: 0, offer: 0, rejected: 0 };
  for (const sheet of sheets) out[sheet.state] += 1;
  return out;
}

/**
 * Owns the pile: the data behind it, and the one animation that rewards adding
 * to it.
 *
 * It lives in the root layout because the counter in the nav has to survive
 * navigation — a card thrown from the ranked list has to land somewhere that is
 * still there after the page changes. That also makes the flight an ordinary
 * same-document animation rather than something that has to cross a route
 * boundary, which is a much harder problem for no gain.
 */

type StackContext = {
  model: StackModel;
  /** Counts from /setup/status — cheap, and already fetched for the nav. */
  counts: SetupStatus["counts"] | null;
  setupIncomplete: boolean;
  /** Where a thrown card lands. */
  pipRef: React.RefObject<HTMLElement | null>;
  /**
   * Record that a job just went out, and throw a card for it.
   * `from` is the rect of the row it left, captured *before* the row moves.
   */
  recordSent: (jobId: number, status: Status, from: DOMRect | null) => void;
  /** Re-read everything. Cheap, all local. */
  refresh: () => void;
  /** Increments when a card lands, so the pile can settle it. */
  landed: number;
};

const EMPTY: StackModel = {
  sheets: [],
  total: 0,
  today: 0,
  target: DEFAULT_TARGET,
  byState: { sent: 0, test: 0, interview: 0, offer: 0, rejected: 0 },
  nextMilestone: 25,
};

const Ctx = createContext<StackContext | null>(null);

export function useStack(): StackContext {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStack must be used inside <StackProvider>");
  return ctx;
}

const SENT: Status[] = [
  "applied",
  "outreach_sent",
  "test",
  "interview",
  "offer",
  "rejected",
];

export function StackProvider({ children }: { children: React.ReactNode }) {
  const [model, setModel] = useState<StackModel>(EMPTY);
  const [counts, setCounts] = useState<SetupStatus["counts"] | null>(null);
  const [setupIncomplete, setSetupIncomplete] = useState(false);
  const [landed, setLanded] = useState(0);
  const pipRef = useRef<HTMLElement | null>(null);
  const target = useRef(DEFAULT_TARGET);

  const refresh = useCallback(() => {
    // Both are local and small. Failing is normal — the backend may simply not
    // be up yet — and an empty pile is the honest thing to show when it isn't.
    api
      .listApplications()
      .then((rows) => setModel(buildStack(rows, target.current)))
      .catch(() => {});
    api
      .setupStatus()
      .then((s) => {
        setCounts(s.counts);
        setSetupIncomplete(!s.ready);
      })
      .catch(() => setCounts(null));
  }, []);

  useEffect(() => {
    const stored = Number(localStorage.getItem("stack.dailyTarget"));
    if (Number.isFinite(stored) && stored > 0) target.current = stored;
    refresh();
  }, [refresh]);

  const recordSent = useCallback(
    (jobId: number, status: Status, from: DOMRect | null) => {
      if (!SENT.includes(status)) {
        // Not a send, but it may have turned a job into a prepared resume or
        // away from one, which changes the hollow sheets.
        refresh();
        return;
      }

      const state = stateOf(status);
      // Only a sheet that is genuinely new is worth throwing. Moving one along
      // the funnel is progress, not another application, so it recolours in
      // place rather than flying across the screen again.
      const isNew = !model.sheets.some((s) => s.jobId === jobId);

      // Optimistic: the pile reacts the instant you act, not a round trip later.
      setModel((prev) => {
        const sheets = prev.sheets.some((s) => s.jobId === jobId)
          ? prev.sheets.map((s) => (s.jobId === jobId ? { ...s, state } : s))
          : [
              ...prev.sheets,
              { jobId, title: "", company: "", appliedAt: new Date(), state },
            ];
        return {
          ...prev,
          sheets,
          total: sheets.length,
          today: prev.today + (isNew ? 1 : 0),
          byState: countStates(sheets),
          nextMilestone: nextMilestone(sheets.length),
        };
      });

      if (isNew) throwCard(jobId, from, pipRef.current, () => setLanded((n) => n + 1));

      // Reconcile with the server once it has caught up, so the titles and the
      // real timestamp replace the optimistic blank.
      window.setTimeout(refresh, 600);
    },
    [refresh, model.sheets],
  );

  const value = useMemo(
    () => ({
      model,
      counts,
      setupIncomplete,
      pipRef,
      recordSent,
      refresh,
      landed,
    }),
    [model, counts, setupIncomplete, recordSent, refresh, landed],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {/* The flight is the sighted reward for sending something; this is the
          same reward for anyone not watching it. It fires whatever the motion
          preference, and from any page, which is why it lives up here rather
          than inside the pile. */}
      <p aria-live="polite" className="sr-only">
        {landed > 0
          ? `Sent. ${model.today} of ${model.target} today. ${model.total} in the stack.`
          : ""}
      </p>
    </Ctx.Provider>
  );
}

/**
 * Throw a sheet of paper from the row you just acted on onto the pile.
 *
 * A clone in a fixed layer rather than the row itself, because the row is about
 * to re-render, move, or vanish behind a filter. The arc matters: a straight
 * line reads as the row being sucked into a slot, while lifting first and
 * falling in reads as something being tossed onto a pile, which is the whole
 * metaphor.
 */
function throwCard(
  jobId: number,
  from: DOMRect | null,
  pip: HTMLElement | null,
  onDone: () => void,
) {
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // No source rect, nowhere to land, or motion turned down: the count still
  // changed, and the aria-live announcement still fires. Only the flourish goes.
  if (reduced || !from || !pip || typeof document === "undefined") {
    onDone();
    pulse(pip, reduced);
    return;
  }

  const layer = document.getElementById("flip-layer");
  if (!layer) {
    onDone();
    return;
  }

  const to = pip.getBoundingClientRect();
  const card = document.createElement("div");
  card.setAttribute("aria-hidden", "true");
  card.className =
    "pointer-events-none fixed rounded-[2px] border border-paper-edge bg-paper shadow-sm";
  card.style.left = `${from.left}px`;
  card.style.top = `${from.top}px`;
  card.style.width = `${Math.min(from.width, 260)}px`;
  card.style.height = `${Math.max(10, Math.min(from.height, 44))}px`;
  layer.appendChild(card);

  const dx = to.left + to.width / 2 - (from.left + Math.min(from.width, 260) / 2);
  const dy = to.top + to.height / 2 - from.top;

  gsap
    .timeline({
      onComplete: () => {
        card.remove();
        onDone();
        pulse(pip, false);
      },
    })
    .to(card, {
      x: dx,
      y: dy,
      scaleX: 0.12,
      scaleY: 0.3,
      rotation: rotation(jobId),
      xPercent: offsetX(jobId) * 0.4,
      duration: DUR.flight,
      ease: EASE.flight,
    })
    // The lift, running against the fall, is what makes it an arc.
    .to(card, { y: dy - 26, duration: DUR.flight * 0.45, ease: "power2.out" }, 0)
    .to(card, { y: dy, duration: DUR.flight * 0.55, ease: "power2.in" }, DUR.flight * 0.45)
    .to(card, { opacity: 0, duration: DUR.fast }, DUR.flight - DUR.fast);
}

/** The counter acknowledging the landing. */
function pulse(pip: HTMLElement | null, reduced: boolean) {
  if (!pip) return;
  if (reduced) {
    // Something must still change visibly. One tick of an attribute, no motion.
    pip.setAttribute("data-just-landed", "");
    window.setTimeout(() => pip.removeAttribute("data-just-landed"), 900);
    return;
  }
  gsap.fromTo(
    pip,
    { scale: 1 },
    { scale: 1.14, duration: 0.12, yoyo: true, repeat: 1, ease: "power2.out" },
  );
}
