"use client";

import { Check, Search, TrendingUp } from "lucide-react";

import { type SkillAnalytics } from "@/lib/api";
import { SkillBar } from "@/components/roadmap/skill-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const ROLE_FAMILIES = [
  { id: "all", label: "All roles" },
  { id: "backend", label: "Backend" },
  { id: "fullstack", label: "Fullstack" },
  { id: "frontend", label: "Frontend" },
  { id: "mobile", label: "Mobile" },
  { id: "devops", label: "DevOps & infra" },
  { id: "data", label: "Data & AI" },
];

/**
 * What the market asks for, split by whether your Knowledge Base can prove it.
 *
 * The missing column is selectable: picking skills here is what drives the
 * simulator, so the two halves of the answer — what is missing, and what it
 * would be worth — stay on one screen.
 */
export function MarketMatrix({
  analytics,
  selectedFamily,
  onFamilyChange,
  selectedCategory,
  onCategoryChange,
  searchQuery,
  onSearchChange,
  selectedSkills,
  onToggleSkill,
  onClearSelection,
}: {
  analytics: SkillAnalytics | null;
  selectedFamily: string;
  onFamilyChange: (id: string) => void;
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedSkills: string[];
  onToggleSkill: (skill: string) => void;
  onClearSelection: () => void;
}) {
  const allMissing = analytics?.top_missing_skills ?? [];
  const allMastered = analytics?.top_mastered_skills ?? [];

  const matches = (skill: { skill: string; category: string }) => {
    const byCategory =
      selectedCategory === "all" || skill.category === selectedCategory;
    const byQuery =
      !searchQuery || skill.skill.toLowerCase().includes(searchQuery.toLowerCase());
    return byCategory && byQuery;
  };

  const filteredMissing = allMissing.filter(matches);
  const filteredMastered = allMastered.filter(matches);

  const categories = [
    "all",
    ...Array.from(new Set([...allMissing, ...allMastered].map((s) => s.category))),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-xs font-medium text-muted-foreground">
            Role family:
          </span>
          {ROLE_FAMILIES.map((rf) => (
            <Button
              key={rf.id}
              variant={selectedFamily === rf.id ? "default" : "outline"}
              size="sm"
              onClick={() => onFamilyChange(rf.id)}
              className="h-7 rounded-full text-xs"
            >
              {rf.label}
            </Button>
          ))}
        </div>

        <div className="relative w-full sm:w-60">
          <Search className="absolute left-2.5 top-2 size-3.5 text-muted-foreground" />
          <Input
            placeholder="Filter skills..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        <span className="mr-1 text-xs font-medium text-muted-foreground">Category:</span>
        {categories.map((cat) => (
          <Badge
            key={cat}
            variant={selectedCategory === cat ? "default" : "outline"}
            className="cursor-pointer text-xs capitalize transition-colors"
            onClick={() => onCategoryChange(cat)}
          >
            {cat}
          </Badge>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-3 lg:col-span-7">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold">
                <span className="size-2 rounded-full bg-amber-500" />
                Asked for, not yet proved
              </h2>
              <p className="text-xs text-muted-foreground">
                Named by active postings, absent from your Knowledge Base. Select any
                to see what learning them would be worth.
              </p>
            </div>
            {selectedSkills.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-muted-foreground"
                onClick={onClearSelection}
              >
                Clear selection ({selectedSkills.length})
              </Button>
            )}
          </div>

          {filteredMissing.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              No gaps match this filter.
            </div>
          ) : (
            <div className="space-y-2">
              {filteredMissing.map((item) => {
                const isSelected = selectedSkills.includes(item.skill);
                return (
                  <div
                    key={item.skill}
                    onClick={() => onToggleSkill(item.skill)}
                    className={`group relative flex cursor-pointer items-center justify-between rounded-lg border p-3.5 transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 shadow-xs"
                        : "hover:border-foreground/30 hover:bg-muted/30"
                    }`}
                  >
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{item.skill}</span>
                        <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                          {item.category}
                        </Badge>
                        {item.potential_score_lift > 0 && (
                          <span className="flex items-center gap-0.5 text-[11px] font-medium text-green-600 dark:text-green-500">
                            <TrendingUp className="size-3" />+{item.potential_score_lift}%
                            on the roles that ask for it
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>
                          Wanted in <strong>{item.frequency}</strong> jobs (
                          {item.percentage}%)
                        </span>
                        {item.sample_companies.length > 0 && (
                          <span>e.g. {item.sample_companies.slice(0, 3).join(", ")}</span>
                        )}
                      </div>
                    </div>

                    <div
                      className={`flex size-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
                        isSelected
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground/40 group-hover:border-foreground"
                      }`}
                    >
                      {isSelected && <Check className="size-3.5 stroke-[3]" />}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="space-y-3 lg:col-span-5">
          <div>
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <span className="size-2 rounded-full bg-green-500" />
              Already covered
            </h2>
            <p className="text-xs text-muted-foreground">
              Skills an accomplishment in your Knowledge Base can back up.
            </p>
          </div>

          {filteredMastered.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Nothing covered matches this filter.
            </div>
          ) : (
            <div className="divide-y rounded-lg border text-sm">
              {filteredMastered.map((item) => (
                <div key={item.skill} className="flex items-center justify-between p-3">
                  <div>
                    <span className="font-medium">{item.skill}</span>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {item.category} · asked for in {item.frequency} postings (
                      {item.percentage}%)
                    </div>
                  </div>
                  <Badge
                    variant="secondary"
                    className="bg-green-500/10 text-xs text-green-700 dark:text-green-400"
                  >
                    <Check className="mr-1 size-3" />
                    Covered
                  </Badge>
                </div>
              ))}
            </div>
          )}

          {analytics?.domain_clusters && analytics.domain_clusters.length > 0 && (
            <div className="mt-4 space-y-3 rounded-lg border p-4">
              <h3 className="text-sm font-medium">By domain</h3>
              <div className="space-y-2.5">
                {analytics.domain_clusters.map((cluster) => {
                  const total = cluster.mastered_count + cluster.missing_count;
                  const pct =
                    total > 0 ? Math.round((cluster.mastered_count / total) * 100) : 0;
                  return (
                    <div key={cluster.category} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium">{cluster.category}</span>
                        <span className="text-muted-foreground">
                          {cluster.mastered_count} / {total} covered ({pct}%)
                        </span>
                      </div>
                      <SkillBar value={pct} className="h-1" />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
