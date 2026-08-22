"use client";

import { useEffect, useState } from "react";
import { Compass, Layers, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";

import {
  api,
  type RoadmapMilestone,
  type SkillAnalytics,
  type SkillRoadmap,
  type SkillSimulationResult,
} from "@/lib/api";
import { GenerateDialog } from "@/components/roadmap/generate-dialog";
import { MarketMatrix } from "@/components/roadmap/market-matrix";
import { OverviewCards } from "@/components/roadmap/overview-cards";
import { RoadmapCard } from "@/components/roadmap/roadmap-card";
import { SimulatorBar } from "@/components/roadmap/simulator-bar";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The market-wide view of what is holding you back.
 *
 * The per-job project idea answers "what would win me this one role?". Nobody
 * can build twenty of those, so this page asks the other question: across every
 * active posting, which few skills are worth the most, and what is the single
 * project that would cover them?
 */
export default function RoadmapPage() {
  const [analytics, setAnalytics] = useState<SkillAnalytics | null>(null);
  const [roadmaps, setRoadmaps] = useState<SkillRoadmap[]>([]);
  const [selectedFamily, setSelectedFamily] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"matrix" | "roadmaps">("matrix");
  const [loading, setLoading] = useState(true);

  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [simResult, setSimResult] = useState<SkillSimulationResult | null>(null);
  const [simulating, setSimulating] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [genSkills, setGenSkills] = useState<string[] | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Bumped by anything that changes what the backend would say — adding a
  // project to the Knowledge Base rescores every job, so the page must re-ask.
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let current = true;
    Promise.all([
      api.getSkillAnalytics(selectedFamily === "all" ? undefined : selectedFamily),
      api.listRoadmaps(),
    ])
      .then(([data, list]) => {
        if (!current) return;
        setAnalytics(data);
        setRoadmaps(list);
        // Open the newest on arrival, but never fight a choice already made.
        setExpandedId((expanded) => expanded ?? list[0]?.id ?? null);
      })
      .catch(() => {}) // backend not reachable yet
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [selectedFamily, reloadToken]);

  // Rescoring every active job takes a moment, so a stale answer can land after
  // a newer one. The guard makes the last request the one that wins.
  useEffect(() => {
    if (selectedSkills.length === 0) return;
    let current = true;
    setSimulating(true);
    api
      .simulateSkills(selectedSkills)
      .then((res) => current && setSimResult(res))
      .catch(() => {})
      .finally(() => {
        if (current) setSimulating(false);
      });
    return () => {
      current = false;
    };
  }, [selectedSkills]);

  function toggleSkill(skill: string) {
    setSelectedSkills((prev) => {
      const next = prev.includes(skill)
        ? prev.filter((s) => s !== skill)
        : [...prev, skill];
      if (next.length === 0) setSimResult(null);
      return next;
    });
  }

  function clearSkills() {
    setSelectedSkills([]);
    setSimResult(null);
  }

  function openGenerator(skills: string[]) {
    setGenSkills(skills);
  }

  async function generate(roleFamily: string, weeks: number) {
    if (!genSkills || genSkills.length === 0) return;

    setGenerating(true);
    try {
      const roadmap = await api.generateRoadmap({
        target_skills: genSkills,
        role_family: roleFamily,
        estimated_weeks: weeks,
      });
      setRoadmaps((prev) => [roadmap, ...prev]);
      setExpandedId(roadmap.id);
      setActiveTab("roadmaps");
      setGenSkills(null);
      clearSkills();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function toggleMilestone(roadmapId: number, milestoneIndex: number) {
    const target = roadmaps.find((r) => r.id === roadmapId);
    const milestone = target?.milestones[milestoneIndex];
    if (!target || !milestone) return;

    const milestones: RoadmapMilestone[] = target.milestones.map((m, i) =>
      i === milestoneIndex ? { ...m, completed: !m.completed } : m,
    );

    try {
      const updated = await api.updateRoadmap(roadmapId, { milestones });
      setRoadmaps((prev) => prev.map((r) => (r.id === roadmapId ? updated : r)));
    } catch {
      toast.error("Could not save that milestone.");
    }
  }

  async function addToKb(roadmapId: number) {
    try {
      const res = await api.completeRoadmapToKb(roadmapId);
      toast.success(res.message);
      setReloadToken((t) => t + 1);
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function deleteRoadmap(roadmapId: number) {
    try {
      await api.deleteRoadmap(roadmapId);
      setRoadmaps((prev) => prev.filter((r) => r.id !== roadmapId));
    } catch (e) {
      toast.error(String(e));
    }
  }

  function copyBullet(text: string) {
    navigator.clipboard.writeText(text);
    toast.success("Copied.");
  }

  const topGaps = (analytics?.top_missing_skills ?? []).slice(0, 3).map((s) => s.skill);

  return (
    <div className="space-y-8 pb-24">
      <div className="space-y-2">
        <PageHeader
          title="Skills and roadmap"
          meta="What every active posting asks for, what your Knowledge Base can prove, and the one project that would close the gap."
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              openGenerator(selectedSkills.length > 0 ? selectedSkills : topGaps)
            }
          >
            <Plus className="mr-1.5 size-3.5" />
            New project
          </Button>
        </PageHeader>

        {loading ? (
          <div className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        ) : (
          analytics && <OverviewCards analytics={analytics} />
        )}
      </div>

      <div className="flex items-center justify-between border-b">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab("matrix")}
            className={`-mb-px flex cursor-pointer items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
              activeTab === "matrix"
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Compass className="size-4" />
            Demand and gaps
          </button>
          <button
            onClick={() => setActiveTab("roadmaps")}
            className={`-mb-px flex cursor-pointer items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
              activeTab === "roadmaps"
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="size-4" />
            Projects
            {roadmaps.length > 0 && (
              <Badge variant="secondary" className="px-1.5 py-0 text-xs">
                {roadmaps.length}
              </Badge>
            )}
          </button>
        </div>
      </div>

      {activeTab === "matrix" && (
        <MarketMatrix
          analytics={analytics}
          selectedFamily={selectedFamily}
          onFamilyChange={setSelectedFamily}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          selectedSkills={selectedSkills}
          onToggleSkill={toggleSkill}
          onClearSelection={clearSkills}
        />
      )}

      {activeTab === "roadmaps" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Projects</h2>
              <p className="text-xs text-muted-foreground">
                Each one covers several gaps at once, in weekly milestones.
              </p>
            </div>
            <Button size="sm" onClick={() => openGenerator(topGaps)}>
              <Sparkles className="mr-1.5 size-3.5" />
              Plan a project
            </Button>
          </div>

          {roadmaps.length === 0 ? (
            <div className="space-y-4 rounded-xl border border-dashed p-12 text-center">
              <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Layers className="size-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold">No projects planned yet</h3>
                <p className="mx-auto max-w-md text-sm text-muted-foreground">
                  Pick the gaps worth closing on the other tab, and this turns them
                  into one project with weekly milestones.
                </p>
              </div>
              <Button onClick={() => openGenerator(topGaps)}>
                <Sparkles className="mr-1.5 size-4" />
                Plan the first one
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              {roadmaps.map((roadmap) => (
                <RoadmapCard
                  key={roadmap.id}
                  roadmap={roadmap}
                  expanded={expandedId === roadmap.id}
                  onToggleExpanded={() =>
                    setExpandedId(expandedId === roadmap.id ? null : roadmap.id)
                  }
                  onToggleMilestone={(idx) => toggleMilestone(roadmap.id, idx)}
                  onAddToKb={() => addToKb(roadmap.id)}
                  onDelete={() => deleteRoadmap(roadmap.id)}
                  onCopyBullet={copyBullet}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {selectedSkills.length > 0 && activeTab === "matrix" && (
        <SimulatorBar
          selectedSkills={selectedSkills}
          result={simResult}
          simulating={simulating}
          onReset={clearSkills}
          onBuildRoadmap={() => openGenerator(selectedSkills)}
        />
      )}

      {genSkills !== null && (
        <GenerateDialog
          skills={genSkills}
          onSkillsChange={setGenSkills}
          generating={generating}
          onGenerate={generate}
          onClose={() => setGenSkills(null)}
        />
      )}
    </div>
  );
}
