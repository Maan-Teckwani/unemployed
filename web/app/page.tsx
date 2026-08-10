"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type SetupStatus } from "@/lib/api";
import { BoardStrip } from "@/components/board/board-strip";
import { Logo } from "@/components/logo";
import { PipelineRunner } from "@/components/pipeline/pipeline-runner";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The control center — the first thing anyone sees.
 *
 * It answers "what do I do next?" for a new user (an ordered checklist) and
 * "is there work waiting?" for a returning one (counts plus a way in). The
 * pipeline buttons live here so the terminal is optional.
 */
export default function Home() {
  const [setup, setSetup] = useState<SetupStatus | null>(null);

  const refresh = useCallback(async () => {
    try {
      setSetup(await api.setupStatus());
    } catch {
      // Backend not reachable yet.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const counts = setup?.counts;
  const nextStep = setup?.steps.find((s) => !s.done);

  return (
    <div className="space-y-8">
      <div className="border-b pb-8">
        <h1>
          <Logo size="hero" />
        </h1>
        <p className="text-muted-foreground mt-3 text-sm max-w-prose">
          Finds jobs you can actually get, scores them so you can see why, and
          writes a tailored resume grounded in work you&apos;ve really done.
          Everything runs on your machine.
        </p>
      </div>

      {/* Returning user: get them straight into the work. */}
      {setup?.ready && (
        <div className="rounded-lg border p-5 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="font-medium">
              {counts?.rankable ?? 0} role
              {counts?.rankable === 1 ? "" : "s"} worth applying to
            </p>
            <p className="text-sm text-muted-foreground mt-0.5">
              {counts?.active_jobs} active jobs from {counts?.companies} companies
              {counts?.applied ? ` · ${counts.applied} applied` : ""}
            </p>
          </div>
          <Link href="/today" className={buttonVariants({ variant: "default" })}>
            Apply today →
          </Link>
        </div>
      )}

      {/* First-time user: the ordered path, with the next step highlighted. */}
      <div className="space-y-3">
        <h2 className="font-medium">
          {setup?.ready ? "Setup" : "Get started"}
        </h2>
        <div className="rounded-lg border divide-y">
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
                {step.detail && (
                  <p className="text-xs text-muted-foreground">{step.detail}</p>
                )}
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
                <span className="text-xs text-muted-foreground">
                  use the buttons below
                </span>
              )}
            </div>
          ))}
          {!setup &&
            Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3.5">
                <Skeleton className="size-5 shrink-0 rounded-full" />
                <Skeleton className="h-3.5 w-48" />
              </div>
            ))}
        </div>
      </div>

      <Separator />

      <div className="space-y-3">
        <div>
          <h2 className="font-medium">Update your jobs</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Fetch pulls new postings from every company you track and scores them
            against your knowledge base in the same run. The slow part is your
            local model reading the job descriptions worth applying to.
          </p>
        </div>
        <PipelineRunner onFinished={refresh} />
      </div>

      <Separator />

      <BoardStrip />

      <p className="text-xs text-muted-foreground">
        Found a job elsewhere?{" "}
        <Link href="/manual-jd" className="underline">
          Paste the description
        </Link>{" "}
        to score it and tailor a resume.
      </p>
    </div>
  );
}
