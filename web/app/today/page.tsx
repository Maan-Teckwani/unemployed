"use client";

import Link from "next/link";
import { useEffect, useRef, useState, ViewTransition } from "react";
import { api, type Match, type Status } from "@/lib/api";
import { remember } from "@/lib/job-cache";
import { gsap, OK, ScrollTrigger, STAGGER, useGSAP } from "@/lib/motion";
import { scoreTone } from "@/lib/score";
import { useRemembered } from "@/lib/use-remembered";
import { FitBreakdown } from "@/components/matches/fit-breakdown";
import { PageHeader } from "@/components/page-header";
import { ListSkeleton } from "@/components/skeletons/list-skeleton";
import { StatusSelect } from "@/components/status-select";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";

/**
 * The daily loop, answering only four questions:
 *   What should I apply to today? Why is it a fit? Generate. Apply.
 *
 * This also absorbed the old /matches page: two nearly identical ranked lists
 * was a distinction only the developer understood. "Show filtered" reveals what
 * was excluded and why, without needing a second page.
 */
export default function TodayPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [hideDone, setHideDone] = useRemembered("today.hideDone", true);
  const [showFiltered, setShowFiltered] = useRemembered("today.showFiltered", false);
  const [loading, setLoading] = useState(true);
  const list = useRef<HTMLDivElement>(null);

  // The remembered toggle arrives one render after mount, so two requests can be
  // in flight at once. Without the guard the slower — and now wrong — answer wins.
  useEffect(() => {
    let current = true;
    setLoading(true);
    api
      .listMatches(50, showFiltered)
      .then((rows) => {
        if (!current) return;
        setMatches(rows);
        // Hand the detail page what this one already knows, so opening a job
        // paints its title immediately instead of behind a skeleton.
        remember(rows.map((m) => m.job));
      })
      .catch(() => {}) // backend not reachable yet
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [showFiltered]);

  function setStatus(jobId: number, status: Status) {
    setMatches((prev) =>
      prev.map((m) => (m.job.id === jobId ? { ...m, status } : m)),
    );
  }

  // "Completed" means you have already dealt with it, whatever the outcome —
  // anything you have sent, plus the ones you decided against. What is left is
  // the actual work: jobs still to look at, and resumes still to send.
  const done = new Set<Status>([
    "applied",
    "outreach_sent",
    "test",
    "interview",
    "offer",
    "rejected",
    "closed",
  ]);
  const visible = hideDone ? matches.filter((m) => !done.has(m.status)) : matches;
  const appliedCount = matches.filter((m) => m.status === "applied").length;

  // Rows arrive as you reach them rather than all at once, which on a list this
  // long is the difference between "it loaded" and "it is loading". Batched so
  // a fast scroll does not queue up fifty separate tweens.
  useGSAP(
    () => {
      if (loading || visible.length === 0) return;
      const mm = gsap.matchMedia();
      mm.add(OK, () => {
        const batch = ScrollTrigger.batch("[data-row]", {
          start: "top 95%",
          onEnter: (rows) =>
            gsap.from(rows, {
              y: 10,
              opacity: 0,
              duration: 0.3,
              stagger: STAGGER,
              ease: "power3.out",
              overwrite: true,
            }),
        });
        return () => batch.forEach((t) => t.kill());
      });
      return () => mm.revert();
    },
    { scope: list, dependencies: [loading, visible.length] },
  );

  return (
    <div className="space-y-8">
      <PageHeader
        title="Apply today"
        meta={
          loading
            ? "Loading…"
            : `${visible.length} role${visible.length === 1 ? "" : "s"} to work through${
                appliedCount > 0 ? ` · ${appliedCount} applied` : ""
              }`
        }
      >
        <Button variant="outline" size="sm" onClick={() => setHideDone(!hideDone)}>
          {hideDone ? "Show" : "Hide"} completed
        </Button>
        <Button variant="outline" size="sm" onClick={() => setShowFiltered(!showFiltered)}>
          {showFiltered ? "Hide" : "Show"} filtered
        </Button>
      </PageHeader>

      {loading && <ListSkeleton rows={6} title={false} />}

      {!loading && (
        <div ref={list} className="rounded-lg border divide-y overflow-hidden">
          {visible.map((m) => (
            <div key={m.job.id} data-row data-flip-source className="px-4 py-3.5">
              <div className="flex items-start gap-3 flex-wrap sm:flex-nowrap">
                <span
                  className={`data w-10 shrink-0 text-data-lg font-medium ${scoreTone(m.score)}`}
                  title="Fit score out of 100"
                >
                  {Math.round(m.score * 100)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <ViewTransition name={`job-${m.job.id}`}>
                      <Link
                        href={`/jobs/${m.job.id}`}
                        className="font-medium hover:underline underline-offset-4"
                      >
                        {m.job.title}
                      </Link>
                    </ViewTransition>
                    {m.job.remote && <Badge variant="secondary">remote</Badge>}
                    {m.tier === "estimated" && (
                      <Badge
                        variant="outline"
                        title="Ranked on semantic + keyword fit; required skills not yet extracted."
                      >
                        estimated
                      </Badge>
                    )}
                    {m.hard_filtered && (
                      <Badge variant="outline">filtered: {m.filter_reason}</Badge>
                    )}
                  </div>
                  <p className="meta mt-1 truncate normal-case tracking-normal">
                    {m.job.company} · {m.job.location || "—"}
                  </p>
                </div>
                <button
                  onClick={() => setOpenId(openId === m.job.id ? null : m.job.id)}
                  aria-expanded={openId === m.job.id}
                  className="text-sm underline underline-offset-4 whitespace-nowrap text-muted-foreground hover:text-foreground"
                >
                  {openId === m.job.id ? "Hide why" : "Why?"}
                </button>
                <StatusSelect
                  jobId={m.job.id}
                  value={m.status}
                  onChange={(s) => setStatus(m.job.id, s)}
                  className="w-36"
                />
              </div>
              {openId === m.job.id && <FitBreakdown match={m} />}
            </div>
          ))}

          {visible.length === 0 && (
            <div className="px-4 py-10 text-center space-y-3">
              <p className="text-sm text-muted-foreground">
                {matches.length === 0
                  ? "No scored jobs yet — fetch and score them from Home."
                  : hideDone
                    ? "All caught up. Everything left is applied or closed."
                    : "All caught up for today."}
              </p>
              <div className="flex gap-2 justify-center">
                <Link
                  href="/"
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  {matches.length === 0 ? "Fetch and score jobs" : "Back to home"}
                </Link>
                <Link
                  href="/manual-jd"
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Paste a job description
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
