import type { Job } from "@/lib/api";

/**
 * What the ranked list already knows about a job, kept for the detail page.
 *
 * Opening a job used to mean staring at a skeleton while the browser re-fetched
 * a title it had just finished drawing. The list has the title, the company and
 * the score in hand, so it leaves them here and the detail page paints its
 * header on the first frame, then fills in the description when it arrives.
 *
 * A module-level Map rather than storage or a store: it should live exactly as
 * long as the tab does, it must be readable *synchronously* during render (a
 * shared-element transition needs the element to exist at swap time, not one
 * effect later), and a stale title is corrected a few hundred milliseconds
 * later by the real fetch anyway.
 */
export type JobSummary = Pick<Job, "id" | "title" | "company" | "location" | "remote">;

const cache = new Map<number, JobSummary>();

export function remember(jobs: JobSummary[]): void {
  for (const job of jobs) cache.set(job.id, job);
}

export function recall(id: number): JobSummary | undefined {
  return cache.get(id);
}
