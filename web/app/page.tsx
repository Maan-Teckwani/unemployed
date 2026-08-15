"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Match, type SetupStatus, type Status } from "@/lib/api";
import { remember } from "@/lib/job-cache";
import { scoreTone } from "@/lib/score";
import { FetchJobs } from "@/components/pipeline/fetch-jobs";
import { usePipeline } from "@/components/pipeline/pipeline-provider";
import { Stack } from "@/components/stack/stack";
import { useStack } from "@/components/stack/stack-provider";
import { StatusSelect } from "@/components/status-select";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

/** How many roles the briefing shows before handing over to the full list. */
const PICKS = 5;

/** Already dealt with, whatever the outcome. Mirrors the Apply today list. */
const DONE = new Set<Status>([
  "applied",
  "outreach_sent",
  "test",
  "interview",
  "offer",
  "rejected",
  "closed",
]);

/**
 * The morning briefing — where you have got to, and what to do next.
 *
 * V2 led with the pile and then made you click through to do anything with it,
 * which meant the first screen of a tool you open every day was a status report
 * you could not act on. The top of the ranked list lives here now, so opening
 * the app and starting work are the same gesture. Everything that used to
 * explain the page — five separate paragraphs of it — is gone: this is the
 * screen you have already read, every day, for weeks.
 */
export default function Home() {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [picks, setPicks] = useState<Match[] | null>(null);
  const { refresh: refreshStack } = useStack();
  const { finished } = usePipeline();

  const refresh = useCallback(async () => {
    try {
      setSetup(await api.setupStatus());
    } catch {
      // Backend not reachable yet.
    }
    try {
      const rows = await api.listMatches(30);
      const open = rows.filter((m) => !DONE.has(m.status)).slice(0, PICKS);
      setPicks(open);
      // Hand the detail page what this one already knows, so opening a job
      // paints its title immediately instead of behind a skeleton.
      remember(open.map((m) => m.job));
    } catch {
      setPicks([]);
    }
    refreshStack();
  }, [refreshStack]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // A finished fetch changes every number on this page.
  useEffect(() => {
    if (finished > 0) refresh();
  }, [finished, refresh]);

  const counts = setup?.counts;
  const nextStep = setup?.steps.find((s) => !s.done);
  const rankable = counts?.rankable ?? 0;

  function setStatus(jobId: number, status: Status) {
    setPicks((prev) =>
      prev ? prev.map((m) => (m.job.id === jobId ? { ...m, status } : m)) : prev,
    );
  }

  return (
    <div className="space-y-8">
      {/* Before anything works, this is the whole page.
          It used to render last — under an empty pile and an empty list — so
          the first-time user read the two things that make no sense yet and
          found the instructions for them at the bottom, if they scrolled. */}
      {setup && !setup.ready && (
        <FirstRun steps={setup.steps} nextId={nextStep?.id} />
      )}

      {/* Where you have got to, and the one control that gets you more to do.
          Fetch sits at the top because nothing on this page exists until it has
          run, and it is the only filled button on the screen so there is never a
          question of what the primary action is. */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-6">
        <div className="min-w-0 flex-1">
          <Stack />
        </div>
        {/* Second on a wide screen, where the eye reaches it after the pile.
            First on a narrow one, where "after" would mean a scroll past the
            whole status block. */}
        <div className="order-first w-full sm:order-none sm:w-auto">
          <FetchJobs counts={counts ?? null} />
        </div>
      </div>

      <Separator />

      {/* The work itself. Two clicks used to stand between opening the app and
          seeing this. */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h2 className="font-medium">Worth applying to</h2>
          {rankable > PICKS && (
            <Link
              href="/today"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              all <span className="data text-foreground">{rankable}</span> roles →
            </Link>
          )}
        </div>

        <div className="rounded-lg border divide-y overflow-hidden">
          {picks === null &&
            Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3.5">
                <Skeleton className="h-4 w-8 shrink-0" />
                <Skeleton className="h-4 flex-1 max-w-xs" />
              </div>
            ))}

          {picks?.map((m) => (
            <div
              key={m.job.id}
              data-flip-source
              className="flex items-center gap-3 px-4 py-3 flex-wrap sm:flex-nowrap"
            >
              <span
                className={`data w-8 shrink-0 text-data-lg font-medium ${scoreTone(m.score)}`}
                title="Fit score out of 100"
              >
                {Math.round(m.score * 100)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/jobs/${m.job.id}`}
                    className="truncate font-medium hover:underline underline-offset-4"
                  >
                    {m.job.title}
                  </Link>
                  {m.job.source === "manual" && (
                    <Badge variant="secondary" title="You pasted this one">
                      pasted
                    </Badge>
                  )}
                </div>
                <p className="meta mt-0.5 truncate normal-case tracking-normal">
                  {m.job.company} · {m.job.location || "—"}
                </p>
              </div>
              <StatusSelect
                jobId={m.job.id}
                value={m.status}
                onChange={(s) => setStatus(m.job.id, s)}
                className="w-36"
              />
            </div>
          ))}

          {picks?.length === 0 && (
            <div className="px-4 py-8 text-center space-y-3">
              <p className="text-sm text-muted-foreground">
                {counts?.scored
                  ? "Nothing left in the ranked list."
                  : "No scored jobs yet."}
              </p>
              <Link
                href="/manual-jd"
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Paste a job description
              </Link>
            </div>
          )}
        </div>
      </section>

    </div>
  );
}

/**
 * The first-run walkthrough.
 *
 * Three facts a first-time user cannot get from the rest of the page: that
 * there is an order, that it is short, and that it only happens once. Without
 * them the home screen is a pile at zero and a list of nothing, which reads as
 * an app that does not work rather than one that has not been told anything
 * yet.
 *
 * Numbered rather than ticked. A checklist says "here are some tasks"; a
 * numbered sequence says the second one will not do anything useful until the
 * first is done, which is the actual constraint — a profile with no knowledge
 * base produces nothing, and scoring before fetching produces nothing.
 *
 * Only the next step gets a filled button. Everything below it is reachable but
 * quiet, so there is exactly one thing to press on a screen the person has
 * never seen.
 */
function FirstRun({
  steps,
  nextId,
}: {
  steps: SetupStatus["steps"];
  nextId?: string;
}) {
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <section className="space-y-4 rounded-lg border bg-paper-shade/25 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="font-medium">Set up, once</h2>
        <p className="data text-data-sm text-muted-foreground">
          {doneCount} of {steps.length} done
        </p>
      </div>

      <p className="max-w-prose text-sm text-muted-foreground">
        In order — each one needs the one before it. After this the app is a
        daily loop: fetch, pick, apply.
      </p>

      <ol className="space-y-1">
        {steps.map((step, i) => {
          const isNext = step.id === nextId;
          return (
            <li
              key={step.id}
              className={`flex items-center gap-3 rounded-md px-3 py-2.5 ${
                isNext ? "bg-background ring-1 ring-border" : ""
              }`}
            >
              <span
                aria-hidden
                className={`data grid size-6 shrink-0 place-items-center rounded-full border text-xs ${
                  step.done
                    ? "border-foreground bg-foreground text-background"
                    : isNext
                      ? "border-foreground text-foreground"
                      : "text-muted-foreground"
                }`}
              >
                {step.done ? "✓" : i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm ${
                    step.done
                      ? "text-muted-foreground line-through decoration-muted-foreground/40"
                      : "font-medium"
                  }`}
                >
                  {step.label}
                </p>
                {step.detail && !step.done && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{step.detail}</p>
                )}
              </div>
              {step.href && (
                <Link
                  href={step.href}
                  className={buttonVariants({
                    variant: isNext ? "default" : "ghost",
                    size: "sm",
                  })}
                >
                  {step.done ? "Edit" : isNext ? "Start →" : "Open"}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
