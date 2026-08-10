"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type SetupStatus } from "@/lib/api";
import { BoardStrip } from "@/components/board/board-strip";
import { Logo } from "@/components/logo";
import { PipelineRunner } from "@/components/pipeline/pipeline-runner";
import { Stack } from "@/components/stack/stack";
import { useStack } from "@/components/stack/stack-provider";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The control center — the first thing anyone sees.
 *
 * V2 leads with the pile rather than the wordmark. The logo said what the app
 * is called, which you already know by the time you have installed it and run
 * it; the pile says what you have done and what is left today, which is the
 * question you actually opened it with. The checklist stays underneath for a
 * first-time user, and folds itself away once every step is done.
 */
export default function Home() {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const { refresh: refreshStack } = useStack();

  const refresh = useCallback(async () => {
    try {
      setSetup(await api.setupStatus());
    } catch {
      // Backend not reachable yet.
    }
    refreshStack();
  }, [refreshStack]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const counts = setup?.counts;
  const nextStep = setup?.steps.find((s) => !s.done);

  return (
    <div className="space-y-8">
      {/* Everything that matters on opening the app, in one screen: who you
          are, what you have sent, what is waiting, and the button that gets
          more. Nothing here should need a scroll to find. */}
      <section className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5 border-b pb-6">
          <div className="min-w-0">
            {/* The wordmark stays full size. It is the one piece of motion in
                the app that is purely a joke, it lands in a glance, and this is
                the page that gets to show it. */}
            <h1>
              <Logo size="hero" />
            </h1>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Finds jobs you can actually get, scores them so you can see why,
              and writes a tailored resume grounded in work you&apos;ve really
              done. Everything runs on your machine.
            </p>
          </div>

          {/* Fetch is the button that makes the whole app have anything in it.
              It used to sit three sections down the page, under a heading, and
              was the single most important control nobody could find. */}
          <div className="space-y-2.5">
            <PipelineRunner onFinished={refresh} />
            {setup?.ready && (
              <Link
                href="/today"
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
              >
                <span className="data text-foreground">{counts?.rankable ?? 0}</span>
                role{counts?.rankable === 1 ? "" : "s"} worth applying to →
              </Link>
            )}
          </div>
        </div>

        <Stack />
      </section>

      <Separator />

      {/* First-time user: the ordered path, with the next step highlighted.
          Once everything is done this collapses to a summary line, because a
          checklist of ticks is furniture on the page you open every morning. */}
      <details className="group" open={!setup?.ready}>
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
          <span>{setup?.ready ? "Setup" : "Get started"}</span>
          {setup?.ready && (
            <span className="meta">all four done · open to change</span>
          )}
        </summary>

        <div className="mt-3 rounded-lg border divide-y">
          {setup?.steps.map((step) => (
            <div key={step.id} className="flex items-center gap-3 px-4 py-3">
              <span
                className={`size-5 shrink-0 rounded-full border grid place-items-center text-xs ${
                  step.done ? "bg-foreground text-background border-foreground" : ""
                }`}
                aria-hidden
              >
                {step.done ? "✓" : ""}
              </span>
              <div className="min-w-0 flex-1">
                <p className={step.done ? "text-sm" : "text-sm font-medium"}>
                  {step.label}
                </p>
                {step.detail && <p className="meta mt-0.5">{step.detail}</p>}
              </div>
              {step.href && (
                <Link
                  href={step.href}
                  className={buttonVariants({
                    variant: step.id === nextStep?.id ? "default" : "outline",
                    size: "sm",
                  })}
                >
                  {step.done ? "Edit" : "Open"}
                </Link>
              )}
              {!step.href && step.action && (
                <span className="meta">use the buttons below</span>
              )}
            </div>
          ))}
          {!setup &&
            Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3.5">
                <Skeleton className="size-5 shrink-0 rounded-full" />
                <Skeleton className="h-3.5 w-48" />
              </div>
            ))}
        </div>
      </details>

      <p className="max-w-prose text-xs text-muted-foreground">
        <strong className="font-medium text-foreground">Fetch jobs</strong>, at the
        top, pulls new postings from every company you track and scores them against
        your knowledge base in the same run. The slow part is your local model
        reading the descriptions worth applying to.
      </p>

      <Separator />

      <BoardStrip />

      <p className="text-xs text-muted-foreground">
        Found a job elsewhere?{" "}
        <Link href="/manual-jd" className="underline underline-offset-4">
          Paste the description
        </Link>{" "}
        to score it and tailor a resume.
      </p>
    </div>
  );
}
