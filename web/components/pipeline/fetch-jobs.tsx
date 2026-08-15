"use client";

import { RefreshCw } from "lucide-react";
import type { SetupStatus } from "@/lib/api";
import { usePipeline } from "@/components/pipeline/pipeline-provider";
import { GoBackTo } from "@/components/go-back-to";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";

/**
 * The button that puts anything in this app at all.
 *
 * It has now been in the wrong place twice. It started as a filled button in
 * the masthead beside the wordmark, with "Find companies" the same size next to
 * it — which read as decoration in the header rather than as the thing to
 * press. Demoting it to a quiet status line under the ranked list overcorrected:
 * an action nothing works without does not belong in a footnote.
 *
 * So it is a primary button, at the top of the page, on its own — the only
 * filled control on the screen. What it acts on (how many jobs, from how many
 * companies) sits underneath as its caption, because the numbers are the reason
 * you would press it and they are useless anywhere else.
 */
export function FetchJobs({ counts }: { counts: SetupStatus["counts"] | null }) {
  const { run, running, start } = usePipeline();

  return (
    <div className="w-full space-y-2 sm:w-56">
      <Button
        onClick={() => start("ingest")}
        disabled={running}
        className="w-full"
        size="lg"
      >
        <RefreshCw className={`size-4 ${running ? "animate-spin" : ""}`} aria-hidden />
        {running ? "Fetching…" : "Fetch jobs"}
      </Button>

      {running && run ? (
        <div className="space-y-1.5">
          <ProgressBar done={run.done} total={run.total} message={run.message} />
          <GoBackTo />
        </div>
      ) : (
        <div className="space-y-0.5 text-xs text-muted-foreground">
          {counts && (
            <p>
              <span className="data text-foreground">
                {counts.active_jobs.toLocaleString()}
              </span>{" "}
              jobs from{" "}
              <span className="data text-foreground">{counts.companies}</span>{" "}
              companies
            </p>
          )}
          <p>About 10 minutes — it scores them too.</p>
          {run?.status === "failed" && (
            <p className="text-amber-600 dark:text-amber-500">⚠ {run.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
