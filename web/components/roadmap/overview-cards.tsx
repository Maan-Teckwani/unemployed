import { type SkillAnalytics } from "@/lib/api";
import { SkillBar } from "@/components/roadmap/skill-bar";
import { Card } from "@/components/ui/card";

/** The four numbers that answer "where do I stand against this market?". */
export function OverviewCards({ analytics }: { analytics: SkillAnalytics }) {
  return (
    <div className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-4">
      <Card className="flex flex-col justify-between border-l-4 border-l-primary p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Market readiness
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight">
            {analytics.market_readiness_pct}%
          </span>
          <span className="text-xs text-muted-foreground">of what is asked for</span>
        </div>
        <SkillBar value={analytics.market_readiness_pct} className="mt-2 h-1.5" />
      </Card>

      <Card className="flex flex-col justify-between p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Jobs read
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight">
            {analytics.total_jobs_analyzed}
          </span>
          <span className="text-xs text-muted-foreground">active roles</span>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          Only postings whose requirements were extracted
        </div>
      </Card>

      <Card className="flex flex-col justify-between p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Skill gaps
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-amber-600 dark:text-amber-500">
            {analytics.missing_skills_count}
          </span>
          <span className="text-xs text-muted-foreground">asked for, not yet proved</span>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          Ranked by how much each would move your scores
        </div>
      </Card>

      <Card className="flex flex-col justify-between p-4">
        <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Covered
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-green-600 dark:text-green-500">
            {analytics.mastered_skills_count}
          </span>
          <span className="text-xs text-muted-foreground">skills</span>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          Evidenced by your Knowledge Base
        </div>
      </Card>
    </div>
  );
}
