"use client";

import {
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Compass,
  Copy,
  ListTodo,
  Rocket,
  Sparkles,
  Trash2,
  Zap,
} from "lucide-react";

import { type SkillRoadmap } from "@/lib/api";
import { SkillBar } from "@/components/roadmap/skill-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/**
 * One project blueprint, collapsed to a single row until you ask for it.
 *
 * Collapsed, a card is a title, where it has got to, and what it would cover —
 * enough to choose between projects with several on screen at once. Everything
 * that only matters once you have chosen lives behind the click.
 *
 * "Add to Knowledge Base" stays disabled until every milestone is ticked. The
 * Knowledge Base is the evidence a resume is built from, and a plan you have
 * not carried out yet is not evidence of anything.
 */
export function RoadmapCard({
  roadmap,
  expanded,
  onToggleExpanded,
  onToggleMilestone,
  onAddToKb,
  onDelete,
  onCopyBullet,
}: {
  roadmap: SkillRoadmap;
  expanded: boolean;
  onToggleExpanded: () => void;
  onToggleMilestone: (milestoneIndex: number) => void;
  onAddToKb: () => void;
  onDelete: () => void;
  onCopyBullet: (text: string) => void;
}) {
  const total = roadmap.milestones.length;
  const done = roadmap.milestones.filter((m) => m.completed).length;
  const progressPct = total > 0 ? Math.round((done / total) * 100) : 0;
  const finished = total > 0 && done === total;

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <button
        type="button"
        onClick={onToggleExpanded}
        aria-expanded={expanded}
        className="w-full cursor-pointer px-4 py-3.5 text-left transition-colors hover:bg-muted/40"
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
          )}

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-medium">{roadmap.title}</span>
              {roadmap.status === "completed" ? (
                <Badge variant="default">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="size-3 text-green-500" />
                    In your Knowledge Base
                  </span>
                </Badge>
              ) : (
                <Badge variant="secondary">In progress</Badge>
              )}
            </div>

            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="size-3" />
                {roadmap.estimated_weeks} weeks
              </span>
              <span className="capitalize">{roadmap.role_family}</span>
              <span>{roadmap.target_skills.join(", ")}</span>
            </div>
          </div>

          <div className="hidden w-40 shrink-0 sm:block">
            <div className="mb-1 text-right text-xs text-muted-foreground">
              {done} of {total} milestones
            </div>
            <SkillBar value={progressPct} className="h-1.5" />
          </div>

          <span
            role="button"
            tabIndex={0}
            aria-label="Delete roadmap"
            title="Delete roadmap"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter" && e.key !== " ") return;
              e.preventDefault();
              e.stopPropagation();
              onDelete();
            }}
            className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
          >
            <Trash2 className="size-4" />
          </span>
        </div>
      </button>

      {expanded && (
        <div className="space-y-6 border-t bg-muted/20 p-6">
          <div className="space-y-4">
            <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {roadmap.summary}
            </p>

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-xs font-medium text-muted-foreground">
                Target skills:
              </span>
              {roadmap.target_skills.map((skill) => (
                <Badge key={skill} variant="secondary" className="text-xs">
                  {skill}
                </Badge>
              ))}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-60 flex-1 space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-medium">Progress</span>
                  <span className="font-medium text-muted-foreground">
                    {done} of {total} milestones done ({progressPct}%)
                  </span>
                </div>
                <SkillBar value={progressPct} className="h-2" />
              </div>

              {roadmap.status !== "completed" && (
                <Button
                  size="sm"
                  onClick={onAddToKb}
                  disabled={!finished}
                  title={
                    finished
                      ? "Add this project to your Knowledge Base"
                      : "Tick every milestone once you have actually built it"
                  }
                >
                  <Rocket className="mr-1.5 size-3.5" />
                  Add to Knowledge Base
                </Button>
              )}
            </div>
          </div>

          {roadmap.architecture && (
            <div className="space-y-2 rounded-lg border bg-card p-4">
              <h4 className="flex items-center gap-2 text-sm font-medium">
                <Compass className="size-4 text-primary" />
                Architecture and data flow
              </h4>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {roadmap.architecture}
              </p>
            </div>
          )}

          <div className="space-y-3">
            <h4 className="flex items-center gap-2 text-sm font-medium">
              <ListTodo className="size-4 text-primary" />
              Weekly milestones
            </h4>

            <div className="space-y-3">
              {roadmap.milestones.map((milestone, mIdx) => (
                <div
                  key={mIdx}
                  className={`rounded-lg border bg-card p-4 transition-all ${
                    milestone.completed ? "border-green-500/30 bg-green-500/5" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                          Week {milestone.week}
                        </span>
                        <span className="text-sm font-medium">{milestone.title}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {milestone.objective}
                      </p>
                    </div>

                    <Button
                      variant={milestone.completed ? "default" : "outline"}
                      size="sm"
                      onClick={() => onToggleMilestone(mIdx)}
                      className={`h-7 text-xs ${
                        milestone.completed
                          ? "bg-green-600 text-white hover:bg-green-700"
                          : ""
                      }`}
                    >
                      {milestone.completed ? (
                        <>
                          <Check className="mr-1 size-3" /> Done
                        </>
                      ) : (
                        "Mark done"
                      )}
                    </Button>
                  </div>

                  {milestone.tasks.length > 0 && (
                    <div className="mt-3 space-y-1.5 border-t pt-2.5">
                      <span className="text-[11px] font-medium uppercase text-muted-foreground">
                        Tasks
                      </span>
                      <ul className="space-y-1 text-xs">
                        {milestone.tasks.map((task, tIdx) => (
                          <li key={tIdx} className="flex items-start gap-2">
                            <span className="text-muted-foreground">•</span>
                            <span>{task}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {milestone.deliverable && (
                    <div className="mt-3 flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-xs">
                      <span className="text-muted-foreground">Deliverable:</span>
                      <span className="font-medium">{milestone.deliverable}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {roadmap.engineering_challenges.length > 0 && (
            <div className="space-y-3">
              <h4 className="flex items-center gap-2 text-sm font-medium">
                <Zap className="size-4 text-amber-500" />
                The hard parts
              </h4>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {roadmap.engineering_challenges.map((c, i) => (
                  <div
                    key={i}
                    className="space-y-1.5 rounded-lg border bg-card p-3.5 text-xs"
                  >
                    <div className="font-semibold text-foreground">{c.challenge}</div>
                    <div className="text-muted-foreground">{c.solution}</div>
                    {c.impact && (
                      <div className="font-medium text-green-600 dark:text-green-500">
                        {c.impact}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-2 rounded-lg border bg-card p-4">
              <div className="flex items-center justify-between">
                <h4 className="flex items-center gap-1.5 text-sm font-medium">
                  <BookOpen className="size-3.5 text-primary" />
                  Resume bullet, once you have built it
                </h4>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => onCopyBullet(roadmap.resume_bullet_preview)}
                  title="Copy bullet point"
                >
                  <Copy className="size-3.5" />
                </Button>
              </div>
              <p className="rounded-md bg-muted/40 p-3 font-mono text-xs italic text-muted-foreground">
                &ldquo;{roadmap.resume_bullet_preview}&rdquo;
              </p>
            </div>

            <div className="space-y-2 rounded-lg border bg-card p-4">
              <h4 className="flex items-center gap-1.5 text-sm font-medium">
                <Sparkles className="size-3.5 text-primary" />
                Worth discussing in an interview
              </h4>
              <ul className="space-y-1.5 text-xs text-muted-foreground">
                {roadmap.interview_talking_points.map((point, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="font-bold text-primary">›</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
