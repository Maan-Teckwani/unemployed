"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Compass,
  Copy,
  Layers,
  ListTodo,
  Plus,
  Rocket,
  Search,
  Sparkles,
  TrendingUp,
  Trash2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import {
  api,
  type MarketSkillItem,
  type RoadmapMilestone,
  type SkillAnalytics,
  type SkillRoadmap,
  type SkillSimulationResult,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Working } from "@/components/working";

const ROLE_FAMILIES = [
  { id: "all", label: "All Roles" },
  { id: "backend", label: "Backend" },
  { id: "fullstack", label: "Fullstack" },
  { id: "frontend", label: "Frontend" },
  { id: "mobile", label: "Mobile" },
  { id: "devops", label: "DevOps & Infra" },
  { id: "data", label: "Data & AI" },
];

function SimpleBar({ value, className = "h-1.5" }: { value: number; className?: string }) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={`w-full overflow-hidden rounded-full bg-muted ${className}`}>
      <div
        className="h-full rounded-full bg-primary transition-all duration-300"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export default function RoadmapPage() {
  const [analytics, setAnalytics] = useState<SkillAnalytics | null>(null);
  const [roadmaps, setRoadmaps] = useState<SkillRoadmap[]>([]);
  const [selectedFamily, setSelectedFamily] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"matrix" | "roadmaps">("matrix");
  const [loading, setLoading] = useState(true);

  // Simulation state
  const [simSelectedSkills, setSimSelectedSkills] = useState<string[]>([]);
  const [simResult, setSimResult] = useState<SkillSimulationResult | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Generate modal / state
  const [generating, setGenerating] = useState(false);
  const [showGenModal, setShowGenModal] = useState(false);
  const [genWeeks, setGenWeeks] = useState(3);
  const [genFamily, setGenFamily] = useState("backend");
  const [customSkillInput, setCustomSkillInput] = useState("");
  const [genSkills, setGenSkills] = useState<string[]>([]);

  // Expanded roadmap details
  const [expandedRoadmapId, setExpandedRoadmapId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [data, list] = await Promise.all([
        api.getSkillAnalytics(selectedFamily === "all" ? undefined : selectedFamily),
        api.listRoadmaps(),
      ]);
      setAnalytics(data);
      setRoadmaps(list);
      if (list.length > 0 && expandedRoadmapId === null) {
        setExpandedRoadmapId(list[0].id);
      }
    } catch {
      // Backend not reachable yet
    } finally {
      setLoading(false);
    }
  }, [selectedFamily, expandedRoadmapId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Run simulation when selected skills change
  useEffect(() => {
    if (simSelectedSkills.length === 0) {
      setSimResult(null);
      return;
    }
    let current = true;
    setSimulating(true);
    api
      .simulateSkills(simSelectedSkills)
      .then((res) => {
        if (current) setSimResult(res);
      })
      .catch(() => {})
      .finally(() => {
        if (current) setSimulating(false);
      });
    return () => {
      current = false;
    };
  }, [simSelectedSkills]);

  function toggleSkillSelection(skill: string) {
    setSimSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill],
    );
  }

  async function handleGenerateRoadmap() {
    const skillsToTarget = genSkills.length > 0 ? genSkills : simSelectedSkills;
    if (skillsToTarget.length === 0) {
      toast.error("Select at least one target skill to build a roadmap.");
      return;
    }

    setGenerating(true);
    try {
      const roadmap = await api.generateRoadmap({
        target_skills: skillsToTarget,
        role_family: genFamily,
        estimated_weeks: genWeeks,
      });
      setRoadmaps((prev) => [roadmap, ...prev]);
      setExpandedRoadmapId(roadmap.id);
      setActiveTab("roadmaps");
      setShowGenModal(false);
      setSimSelectedSkills([]);
      toast.success("Learning roadmap blueprint generated!");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function toggleMilestoneTask(
    roadmapId: number,
    milestoneIndex: number,
  ) {
    const target = roadmaps.find((r) => r.id === roadmapId);
    if (!target) return;

    const newMilestones = JSON.parse(JSON.stringify(target.milestones)) as RoadmapMilestone[];
    const milestone = newMilestones[milestoneIndex];
    if (!milestone) return;

    milestone.completed = !milestone.completed;

    try {
      const updated = await api.updateRoadmap(roadmapId, {
        milestones: newMilestones,
      });
      setRoadmaps((prev) => prev.map((r) => (r.id === roadmapId ? updated : r)));
    } catch {
      toast.error("Failed to update milestone status.");
    }
  }

  async function handleCompleteToKb(roadmapId: number) {
    try {
      const res = await api.completeRoadmapToKb(roadmapId);
      toast.success(res.message);
      const [updatedList, updatedAnalytics] = await Promise.all([
        api.listRoadmaps(),
        api.getSkillAnalytics(selectedFamily === "all" ? undefined : selectedFamily),
      ]);
      setRoadmaps(updatedList);
      setAnalytics(updatedAnalytics);
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function handleDeleteRoadmap(roadmapId: number) {
    try {
      await api.deleteRoadmap(roadmapId);
      setRoadmaps((prev) => prev.filter((r) => r.id !== roadmapId));
      toast.success("Roadmap removed.");
    } catch (e) {
      toast.error(String(e));
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  }

  const allMissing = analytics?.top_missing_skills ?? [];
  const allMastered = analytics?.top_mastered_skills ?? [];

  const filteredMissing = allMissing.filter((s) => {
    const matchesCat = selectedCategory === "all" || s.category === selectedCategory;
    const matchesQuery = !searchQuery || s.skill.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesQuery;
  });

  const filteredMastered = allMastered.filter((s) => {
    const matchesCat = selectedCategory === "all" || s.category === selectedCategory;
    const matchesQuery = !searchQuery || s.skill.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesQuery;
  });

  const categories = [
    "all",
    ...Array.from(new Set([...allMissing, ...allMastered].map((s) => s.category))),
  ];

  return (
    <div className="space-y-8 pb-24">
      {/* Top Banner & Overview */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-serif text-3xl tracking-tight">Skills & Learning Roadmap</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Cross-market deficit analytics, real-time score lift simulation, and high-signal project blueprints.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setGenSkills(
                  simSelectedSkills.length > 0
                    ? simSelectedSkills
                    : allMissing.slice(0, 3).map((s) => s.skill),
                );
                setShowGenModal(true);
              }}
            >
              <Plus className="mr-1.5 size-3.5" />
              New Project Roadmap
            </Button>
          </div>
        </div>

        {/* Top Metric Cards */}
        {loading ? (
          <div className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        ) : (
          analytics && (
            <div className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-4">
              <Card className="p-4 border-l-4 border-l-primary flex flex-col justify-between">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Market Readiness
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold tracking-tight">
                    {analytics.market_readiness_pct}%
                  </span>
                  <span className="text-xs text-muted-foreground">match coverage</span>
                </div>
                <SimpleBar value={analytics.market_readiness_pct} className="mt-2 h-1.5" />
              </Card>

              <Card className="p-4 flex flex-col justify-between">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Jobs Analyzed
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold tracking-tight">
                    {analytics.total_jobs_analyzed}
                  </span>
                  <span className="text-xs text-muted-foreground">active roles</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Across company ATS boards
                </div>
              </Card>

              <Card className="p-4 flex flex-col justify-between">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Top Missing Gaps
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold tracking-tight text-amber-600 dark:text-amber-500">
                    {analytics.top_missing_skills.length}
                  </span>
                  <span className="text-xs text-muted-foreground">skills needed</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Dominating active job postings
                </div>
              </Card>

              <Card className="p-4 flex flex-col justify-between">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Mastered in KB
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold tracking-tight text-green-600 dark:text-green-500">
                    {analytics.top_mastered_skills.length}
                  </span>
                  <span className="text-xs text-muted-foreground">verified skills</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Proved in your Knowledge Base
                </div>
              </Card>
            </div>
          )
        )}
      </div>

      {/* Main Tabs */}
      <div className="border-b flex items-center justify-between">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab("matrix")}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 -mb-px flex items-center gap-2 cursor-pointer ${
              activeTab === "matrix"
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Compass className="size-4" />
            Market Skill Demand & Gaps
          </button>
          <button
            onClick={() => setActiveTab("roadmaps")}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 -mb-px flex items-center gap-2 cursor-pointer ${
              activeTab === "roadmaps"
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="size-4" />
            Project Learning Roadmaps
            {roadmaps.length > 0 && (
              <Badge variant="secondary" className="px-1.5 py-0 text-xs">
                {roadmaps.length}
              </Badge>
            )}
          </button>
        </div>
      </div>

      {/* TAB 1: MARKET SKILL MATRIX */}
      {activeTab === "matrix" && (
        <div className="space-y-6">
          {/* Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground font-medium mr-1">Role Family:</span>
              {ROLE_FAMILIES.map((rf) => (
                <Button
                  key={rf.id}
                  variant={selectedFamily === rf.id ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedFamily(rf.id)}
                  className="h-7 text-xs rounded-full"
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
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 pl-8 text-xs"
              />
            </div>
          </div>

          {/* Category Chips */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-xs text-muted-foreground font-medium mr-1">Category:</span>
            {categories.map((cat) => (
              <Badge
                key={cat}
                variant={selectedCategory === cat ? "default" : "outline"}
                className="cursor-pointer text-xs capitalize transition-colors"
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </Badge>
            ))}
          </div>

          {/* Dual Skill Columns: Missing Gaps vs Mastered */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Missing High-Leverage Skills (7 cols) */}
            <div className="space-y-3 lg:col-span-7">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-base flex items-center gap-2">
                    <span className="size-2 rounded-full bg-amber-500" />
                    High-Leverage Skill Deficits
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    Demanded by active postings, not yet evidenced in your KB. Select to simulate score lift.
                  </p>
                </div>
                {simSelectedSkills.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs h-7 text-muted-foreground"
                    onClick={() => setSimSelectedSkills([])}
                  >
                    Clear selection ({simSelectedSkills.length})
                  </Button>
                )}
              </div>

              {filteredMissing.length === 0 ? (
                <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No missing skills found for this filter.
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredMissing.map((item) => {
                    const isSelected = simSelectedSkills.includes(item.skill);
                    return (
                      <div
                        key={item.skill}
                        onClick={() => toggleSkillSelection(item.skill)}
                        className={`group relative flex items-center justify-between rounded-lg border p-3.5 transition-all cursor-pointer ${
                          isSelected
                            ? "border-primary bg-primary/5 shadow-xs"
                            : "hover:border-foreground/30 hover:bg-muted/30"
                        }`}
                      >
                        <div className="space-y-1 pr-4">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{item.skill}</span>
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                              {item.category}
                            </Badge>
                            {item.potential_score_lift > 0 && (
                              <span className="text-[11px] font-medium text-green-600 dark:text-green-500 flex items-center gap-0.5">
                                <TrendingUp className="size-3" />
                                +{item.potential_score_lift}% on target roles
                              </span>
                            )}

                          </div>

                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span>
                              Wanted in <strong>{item.frequency}</strong> jobs ({item.percentage}%)
                            </span>
                            {item.sample_companies.length > 0 && (
                              <span>
                                e.g. {item.sample_companies.slice(0, 3).join(", ")}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <div
                            className={`size-5 rounded-md border flex items-center justify-center transition-colors ${
                              isSelected
                                ? "bg-primary border-primary text-primary-foreground"
                                : "border-muted-foreground/40 group-hover:border-foreground"
                            }`}
                          >
                            {isSelected && <Check className="size-3.5 stroke-[3]" />}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Mastered Skills (5 cols) */}
            <div className="space-y-3 lg:col-span-5">
              <div>
                <h2 className="font-semibold text-base flex items-center gap-2">
                  <span className="size-2 rounded-full bg-green-500" />
                  Mastered Skills (In Knowledge Base)
                </h2>
                <p className="text-xs text-muted-foreground">
                  Technologies verified by accomplishments in your profile.
                </p>
              </div>

              {filteredMastered.length === 0 ? (
                <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No mastered skills found matching criteria.
                </div>
              ) : (
                <div className="rounded-lg border divide-y text-sm">
                  {filteredMastered.map((item) => (
                    <div
                      key={item.skill}
                      className="flex items-center justify-between p-3"
                    >
                      <div>
                        <span className="font-medium">{item.skill}</span>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {item.category} · {item.frequency} market postings ({item.percentage}%)
                        </div>
                      </div>
                      <Badge variant="secondary" className="text-xs text-green-700 dark:text-green-400 bg-green-500/10">
                        <Check className="mr-1 size-3" />
                        Mastered
                      </Badge>
                    </div>
                  ))}
                </div>
              )}

              {/* Domain Mastery Clusters */}
              {analytics?.domain_clusters && (
                <div className="rounded-lg border p-4 space-y-3 mt-4">
                  <h3 className="font-medium text-sm">Domain Mastery Breakdown</h3>
                  <div className="space-y-2.5">
                    {analytics.domain_clusters.map((cluster) => {
                      const total = cluster.mastered_count + cluster.missing_count;
                      const pct = total > 0 ? Math.round((cluster.mastered_count / total) * 100) : 0;
                      return (
                        <div key={cluster.category} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="font-medium">{cluster.category}</span>
                            <span className="text-muted-foreground">
                              {cluster.mastered_count} / {total} mastered ({pct}%)
                            </span>
                          </div>
                          <SimpleBar value={pct} className="h-1" />
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: LEARNING ROADMAPS */}
      {activeTab === "roadmaps" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-lg">Project Learning Roadmaps</h2>
              <p className="text-xs text-muted-foreground">
                Actionable multi-week engineering blueprints tailored to bridge multiple skill gaps at once.
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => {
                setGenSkills(allMissing.slice(0, 3).map((s) => s.skill));
                setShowGenModal(true);
              }}
            >
              <Sparkles className="mr-1.5 size-3.5" />
              Generate New Blueprint
            </Button>
          </div>

          {roadmaps.length === 0 ? (
            <div className="rounded-xl border border-dashed p-12 text-center space-y-4">
              <div className="mx-auto size-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                <Layers className="size-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-semibold text-base">No learning roadmaps generated yet</h3>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  Pick high-demand missing skills from the Market Skill Matrix to generate a structured 2-to-4 week project blueprint.
                </p>
              </div>
              <Button
                onClick={() => {
                  setGenSkills(allMissing.slice(0, 3).map((s) => s.skill));
                  setShowGenModal(true);
                }}
              >
                <Sparkles className="mr-1.5 size-4" />
                Generate First Roadmap
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              {roadmaps.map((roadmap) => {
                const isExpanded = expandedRoadmapId === roadmap.id;
                const totalMilestones = roadmap.milestones.length;
                const completedMilestones = roadmap.milestones.filter((m) => m.completed).length;
                const progressPct =
                  totalMilestones > 0
                    ? Math.round((completedMilestones / totalMilestones) * 100)
                    : 0;

                return (
                  <Card key={roadmap.id} className="overflow-hidden border-2">
                    {/* Header Strip */}
                    <div className="p-6 space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-lg">{roadmap.title}</h3>
                            <Badge variant={roadmap.status === "completed" ? "default" : "secondary"}>
                              {roadmap.status === "completed" ? (
                                <span className="flex items-center gap-1">
                                  <CheckCircle2 className="size-3 text-green-500" />
                                  Completed
                                </span>
                              ) : (
                                "In Progress"
                              )}
                            </Badge>
                            <Badge variant="outline" className="capitalize text-xs">
                              {roadmap.role_family}
                            </Badge>
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="size-3" />
                              {roadmap.estimated_weeks} weeks
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">
                            {roadmap.summary}
                          </p>
                        </div>

                        <div className="flex items-center gap-2">
                          {roadmap.status !== "completed" && (
                            <Button
                              size="sm"
                              variant="default"
                              onClick={() => handleCompleteToKb(roadmap.id)}
                            >
                              <Rocket className="mr-1.5 size-3.5" />
                              Add to Knowledge Base
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleDeleteRoadmap(roadmap.id)}
                            className="text-muted-foreground hover:text-destructive"
                            title="Delete roadmap"
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </div>

                      {/* Target Skills Tags */}
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs text-muted-foreground font-medium mr-1">Target Skills:</span>
                        {roadmap.target_skills.map((skill) => (
                          <Badge key={skill} variant="secondary" className="text-xs">
                            {skill}
                          </Badge>
                        ))}
                      </div>

                      {/* Progress Bar */}
                      <div className="space-y-1.5 pt-2">
                        <div className="flex justify-between text-xs">
                          <span className="font-medium">Milestone Progress</span>
                          <span className="text-muted-foreground font-medium">
                            {completedMilestones} of {totalMilestones} phases complete ({progressPct}%)
                          </span>
                        </div>
                        <SimpleBar value={progressPct} className="h-2" />
                      </div>

                      <div className="flex justify-center pt-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpandedRoadmapId(isExpanded ? null : roadmap.id)}
                          className="text-xs text-muted-foreground"
                        >
                          {isExpanded ? (
                            <>
                              Hide blueprint details <ChevronUp className="ml-1 size-3.5" />
                            </>
                          ) : (
                            <>
                              Show full blueprint & milestones <ChevronDown className="ml-1 size-3.5" />
                            </>
                          )}
                        </Button>
                      </div>
                    </div>

                    {/* Expandable Body */}
                    {isExpanded && (
                      <div className="border-t bg-muted/20 p-6 space-y-6">
                        {/* System Architecture */}
                        {roadmap.architecture && (
                          <div className="rounded-lg border bg-card p-4 space-y-2">
                            <h4 className="font-medium text-sm flex items-center gap-2">
                              <Compass className="size-4 text-primary" />
                              System Architecture & Data Flow
                            </h4>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              {roadmap.architecture}
                            </p>
                          </div>
                        )}

                        {/* Weekly Milestones */}
                        <div className="space-y-3">
                          <h4 className="font-medium text-sm flex items-center gap-2">
                            <ListTodo className="size-4 text-primary" />
                            Weekly Implementation Milestones
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
                                      <span className="font-medium text-sm">{milestone.title}</span>
                                    </div>
                                    <p className="text-xs text-muted-foreground">{milestone.objective}</p>
                                  </div>

                                  <Button
                                    variant={milestone.completed ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => toggleMilestoneTask(roadmap.id, mIdx)}
                                    className={`h-7 text-xs ${
                                      milestone.completed ? "bg-green-600 hover:bg-green-700 text-white" : ""
                                    }`}
                                  >
                                    {milestone.completed ? (
                                      <>
                                        <Check className="mr-1 size-3" /> Done
                                      </>
                                    ) : (
                                      "Mark Complete"
                                    )}
                                  </Button>
                                </div>

                                {/* Task list */}
                                {milestone.tasks.length > 0 && (
                                  <div className="mt-3 space-y-1.5 border-t pt-2.5">
                                    <span className="text-[11px] font-medium text-muted-foreground uppercase">
                                      Key Engineering Tasks:
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

                                {/* Deliverable */}
                                {milestone.deliverable && (
                                  <div className="mt-3 rounded-md bg-muted/50 px-3 py-2 text-xs flex items-center justify-between">
                                    <span className="text-muted-foreground">Deliverable:</span>
                                    <span className="font-medium">{milestone.deliverable}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Engineering Challenges */}
                        {roadmap.engineering_challenges.length > 0 && (
                          <div className="space-y-3">
                            <h4 className="font-medium text-sm flex items-center gap-2">
                              <Zap className="size-4 text-amber-500" />
                              Core Engineering Challenges Solved
                            </h4>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                              {roadmap.engineering_challenges.map((c, i) => (
                                <div key={i} className="rounded-lg border bg-card p-3.5 space-y-1.5 text-xs">
                                  <div className="font-semibold text-foreground">{c.challenge}</div>
                                  <div className="text-muted-foreground">{c.solution}</div>
                                  {c.impact && (
                                    <div className="text-green-600 dark:text-green-500 font-medium">
                                      Impact: {c.impact}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* STAR Resume Bullet & Interview Points */}
                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                          {/* Resume Bullet */}
                          <div className="rounded-lg border bg-card p-4 space-y-2">
                            <div className="flex items-center justify-between">
                              <h4 className="font-medium text-sm flex items-center gap-1.5">
                                <BookOpen className="size-3.5 text-primary" />
                                Ready-to-Use STAR Resume Bullet
                              </h4>
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => copyToClipboard(roadmap.resume_bullet_preview)}
                                title="Copy bullet point"
                              >
                                <Copy className="size-3.5" />
                              </Button>
                            </div>
                            <p className="text-xs bg-muted/40 p-3 rounded-md italic font-mono text-muted-foreground">
                              &ldquo;{roadmap.resume_bullet_preview}&rdquo;
                            </p>
                          </div>

                          {/* Interview Talking Points */}
                          <div className="rounded-lg border bg-card p-4 space-y-2">
                            <h4 className="font-medium text-sm flex items-center gap-1.5">
                              <Sparkles className="size-3.5 text-primary" />
                              Interview Discussion Points
                            </h4>
                            <ul className="space-y-1.5 text-xs text-muted-foreground">
                              {roadmap.interview_talking_points.map((point, idx) => (
                                <li key={idx} className="flex items-start gap-2">
                                  <span className="text-primary font-bold">›</span>
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
              })}
            </div>
          )}
        </div>
      )}

      {/* Floating Simulation Bar (when skills are selected) */}
      {simSelectedSkills.length > 0 && activeTab === "matrix" && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-[92%] max-w-3xl rounded-xl border bg-card/95 p-4 shadow-xl backdrop-blur-md transition-all">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                  Live Skill Simulator
                </span>
                <Badge variant="default" className="text-xs px-2 py-0">
                  {simSelectedSkills.length} skills selected
                </Badge>
              </div>

              {simulating ? (
                <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <span className="size-2 rounded-full bg-primary animate-ping" />
                  Calculating exact market score lift...
                </div>
              ) : simResult ? (
                <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span>
                    Score jumps:{" "}
                    <strong className="text-foreground">{simResult.previous_avg_score}%</strong> →{" "}
                    <strong className="text-green-600 dark:text-green-500 font-bold">
                      {simResult.new_avg_score}%
                    </strong>{" "}
                    ({simResult.avg_lift >= 0 ? "+" : ""}{simResult.avg_lift}%)
                  </span>
                  {simResult.unlocked_jobs_count > 0 && (
                    <span className="text-foreground font-medium">
                      🎯 Unlocks {simResult.unlocked_jobs_count} top roles!
                    </span>
                  )}
                </div>
              ) : null}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSimSelectedSkills([])}
                className="text-xs"
              >
                Reset
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setGenSkills(simSelectedSkills);
                  setShowGenModal(true);
                }}
                className="text-xs"
              >
                <Sparkles className="mr-1.5 size-3.5" />
                Generate Roadmap for These Skills
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Generate Roadmap Modal */}
      {showGenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-lg">Generate Project Learning Roadmap</h3>
                <p className="text-xs text-muted-foreground">
                  Builds a multi-week engineering project unifying these target skills.
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setShowGenModal(false)}
              >
                ✕
              </Button>
            </div>

            {generating ? (
              <Working label="Designing a production-grade multi-skill project blueprint..." />
            ) : (
              <div className="space-y-4">
                {/* Target Skills */}
                <div className="space-y-2">
                  <Label className="text-xs">Target Skills to Bridge</Label>
                  <div className="flex flex-wrap gap-1.5 min-h-12 rounded-md border p-2 bg-muted/20">
                    {genSkills.map((s) => (
                      <Badge key={s} variant="secondary" className="text-xs flex items-center gap-1">
                        {s}
                        <button
                          onClick={() => setGenSkills(genSkills.filter((x) => x !== s))}
                          className="hover:text-destructive cursor-pointer"
                        >
                          ✕
                        </button>
                      </Badge>
                    ))}
                  </div>

                  <div className="flex gap-2">
                    <Input
                      placeholder="Add custom skill (e.g. Redis, Kafka)..."
                      value={customSkillInput}
                      onChange={(e) => setCustomSkillInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && customSkillInput.trim()) {
                          e.preventDefault();
                          if (!genSkills.includes(customSkillInput.trim())) {
                            setGenSkills([...genSkills, customSkillInput.trim()]);
                          }
                          setCustomSkillInput("");
                        }
                      }}
                      className="h-8 text-xs"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (customSkillInput.trim() && !genSkills.includes(customSkillInput.trim())) {
                          setGenSkills([...genSkills, customSkillInput.trim()]);
                          setCustomSkillInput("");
                        }
                      }}
                      className="h-8 text-xs"
                    >
                      Add
                    </Button>
                  </div>
                </div>

                {/* Role Family & Timeline */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Target Role Family</Label>
                    <select
                      value={genFamily}
                      onChange={(e) => setGenFamily(e.target.value)}
                      className="w-full rounded-md border bg-card px-3 py-1.5 text-xs"
                    >
                      {ROLE_FAMILIES.filter((f) => f.id !== "all").map((f) => (
                        <option key={f.id} value={f.id}>
                          {f.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs">Project Scope (Timeline)</Label>
                    <select
                      value={genWeeks}
                      onChange={(e) => setGenWeeks(Number(e.target.value))}
                      className="w-full rounded-md border bg-card px-3 py-1.5 text-xs"
                    >
                      <option value={2}>2 Weeks (Fast Track)</option>
                      <option value={3}>3 Weeks (Balanced Blueprint)</option>
                      <option value={4}>4 Weeks (Deep Production System)</option>
                    </select>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t">
                  <Button variant="outline" size="sm" onClick={() => setShowGenModal(false)}>
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleGenerateRoadmap} disabled={genSkills.length === 0}>
                    <Sparkles className="mr-1.5 size-3.5" />
                    Generate Roadmap
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
