"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { usePeople } from "./people-provider";
import { orderWall } from "@/lib/wall-order";
import type { CrowdPage, SignupRow } from "@/lib/db";

/**
 * The wall, as the browser sees it: one page of faces, the real headcount, and
 * a way to ask for the next page.
 *
 * Everything that draws faces reads from here, so the hero crowd and the wall
 * itself page in the same way and cannot disagree about how many people there
 * are.
 *
 * The total is shipped separately from the rows on purpose. Sending every row
 * would be a request that grows without limit and one avatar image per person;
 * counting in the database is one cheap number that stays true no matter how
 * many people are on the wall.
 */

// Matches CROWD_PAGE on the server. Not imported from there, because lib/db is
// server-only and importing a value out of it would pull Neon into the bundle.
const PAGE = 200;

/** How close to the end of the loaded rows counts as "about to run out". */
const RUNWAY = 600;

export function useCrowd(page: CrowdPage, me: SignupRow | null) {
  const { added } = usePeople();

  const [rows, setRows] = useState(page.people);
  const [cursor, setCursor] = useState(page.cursor);
  const [loading, setLoading] = useState(false);

  // A fresh server render (someone edited their profile, or joined and came
  // back) hands down a new array. Without this the component would keep showing
  // the page it mounted with, which is the wrong answer stated confidently.
  const [rendered, setRendered] = useState(page.people);
  if (rendered !== page.people) {
    setRendered(page.people);
    setRows(page.people);
    setCursor(page.cursor);
  }

  // `loading` drives the text under the wall; this stops a burst of scroll
  // events from firing the same request several times before that state lands.
  const busy = useRef(false);

  const loadMore = useCallback(async () => {
    if (busy.current || cursor === null) return;
    busy.current = true;
    setLoading(true);
    try {
      const res = await fetch(`/api/signups?limit=${PAGE}&cursor=${encodeURIComponent(cursor)}`);
      if (!res.ok) return;
      const data = (await res.json()) as { signups: SignupRow[]; nextCursor: string | null };
      setRows((prev) => [...prev, ...data.signups]);
      // Coalesced rather than assigned straight through: a response from an
      // older deployment, which a CDN can still be holding for a few seconds
      // after a release, has no `nextCursor` at all. Undefined would not equal
      // null, so paging would think it had more to fetch and ask for a cursor
      // of "undefined" forever.
      setCursor(data.nextCursor ?? null);
    } catch {
      // Same call the server reads make: a wall that stops growing is better
      // than an error banner thrown over the faces. The cursor is untouched, so
      // the next scroll tries again.
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }, [cursor]);

  // You, then the people who built this, then whoever joined while you were
  // looking, then the wall. The rule itself lives in lib/wall-order so the hero
  // and the wall page cannot drift apart, and so it can be tested.
  const people = useMemo(
    () => orderWall({ me, pinned: page.pinned, added, rows }),
    [me, page.pinned, added, rows],
  );

  // Anyone who joined in this tab is not in the number the server counted.
  const extra = added.filter((row) => !rows.some((known) => known.id === row.id)).length;

  return {
    people,
    total: page.total + extra,
    loading,
    done: cursor === null,
    loadMore,
  };
}

/**
 * Load the next page when a scrolling surface is close to running out.
 *
 * Checked after every render as well as on scroll, because a page of faces can
 * be shorter than the surface showing it. Without the render-time check the
 * wall would sit there, unscrollable, with nothing to trigger the fetch that
 * would make it scrollable.
 */
export function useLoadOnApproach(
  ref: React.RefObject<HTMLElement | null>,
  axis: "x" | "y",
  { done, loadMore, count }: { done: boolean; loadMore: () => void; count: number },
) {
  const check = useCallback(() => {
    const el = ref.current;
    if (!el || done) return;
    const used = axis === "x" ? el.scrollLeft + el.clientWidth : el.scrollTop + el.clientHeight;
    const size = axis === "x" ? el.scrollWidth : el.scrollHeight;
    if (used >= size - RUNWAY) loadMore();
  }, [ref, axis, done, loadMore]);

  useEffect(() => {
    check();
  }, [check, count]);

  return check;
}
