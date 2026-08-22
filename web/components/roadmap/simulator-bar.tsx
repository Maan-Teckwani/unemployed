"use client";

import { Sparkles } from "lucide-react";

import { type SkillSimulationResult } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * What the selected skills would be worth, rescored against every active job.
 *
 * Both scores come from the same scorer on the backend, so the difference is
 * the skills and nothing else.
 */
export function SimulatorBar({
  selectedSkills,
  result,
  simulating,
  onReset,
  onBuildRoadmap,
}: {
  selectedSkills: string[];
  result: SkillSimulationResult | null;
  simulating: boolean;
  onReset: () => void;
  onBuildRoadmap: () => void;
}) {
  return (
    <div className="fixed bottom-6 left-1/2 z-40 w-[92%] max-w-3xl -translate-x-1/2 rounded-xl border bg-card/95 p-4 shadow-xl backdrop-blur-md">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              If you learned these
            </span>
            <Badge variant="default" className="px-2 py-0 text-xs">
              {selectedSkills.length} selected
            </Badge>
          </div>

          {simulating ? (
            <div
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
              role="status"
              aria-live="polite"
            >
              <span className="size-2 animate-ping rounded-full bg-primary" />
              Rescoring every active job...
            </div>
          ) : result ? (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>
                Average match{" "}
                <strong className="text-foreground">{result.previous_avg_score}%</strong>{" "}
                &rarr;{" "}
                <strong className="font-bold text-green-600 dark:text-green-500">
                  {result.new_avg_score}%
                </strong>{" "}
                ({result.avg_lift >= 0 ? "+" : ""}
                {result.avg_lift})
              </span>
              {result.unlocked_jobs_count > 0 && (
                <span className="font-medium text-foreground">
                  {result.unlocked_jobs_count} more{" "}
                  {result.unlocked_jobs_count === 1 ? "role crosses" : "roles cross"} 60%
                </span>
              )}
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onReset} className="text-xs">
            Reset
          </Button>
          <Button size="sm" onClick={onBuildRoadmap} className="text-xs">
            <Sparkles className="mr-1.5 size-3.5" />
            Plan a project for these
          </Button>
        </div>
      </div>
    </div>
  );
}
