"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";

import { ROLE_FAMILIES } from "@/components/roadmap/market-matrix";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Working } from "@/components/working";

const WEEKS = [
  { value: "2", label: "2 weeks (tight)" },
  { value: "3", label: "3 weeks (balanced)" },
  { value: "4", label: "4 weeks (deep)" },
];

/** Confirm what to build for, before spending a generation on it. */
export function GenerateDialog({
  skills,
  onSkillsChange,
  generating,
  onGenerate,
  onClose,
}: {
  skills: string[];
  onSkillsChange: (skills: string[]) => void;
  generating: boolean;
  onGenerate: (roleFamily: string, weeks: number) => void;
  onClose: () => void;
}) {
  const [roleFamily, setRoleFamily] = useState("backend");
  const [weeks, setWeeks] = useState("3");
  const [custom, setCustom] = useState("");

  function addCustom() {
    const skill = custom.trim();
    if (!skill || skills.includes(skill)) return;
    onSkillsChange([...skills, skill]);
    setCustom("");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg space-y-5 rounded-xl border bg-card p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Plan a project</h3>
            <p className="text-xs text-muted-foreground">
              One multi-week project that covers all of these skills at once.
            </p>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>

        {generating ? (
          <Working label="Working out what to build..." />
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-xs">Skills to cover</Label>
              <div className="flex min-h-12 flex-wrap gap-1.5 rounded-md border bg-muted/20 p-2">
                {skills.map((s) => (
                  <Badge
                    key={s}
                    variant="secondary"
                    className="flex items-center gap-1 text-xs"
                  >
                    {s}
                    <button
                      onClick={() => onSkillsChange(skills.filter((x) => x !== s))}
                      className="cursor-pointer hover:text-destructive"
                      aria-label={`Remove ${s}`}
                    >
                      ✕
                    </button>
                  </Badge>
                ))}
              </div>

              <div className="flex gap-2">
                <Input
                  placeholder="Add a skill (e.g. Redis, Kafka)..."
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCustom();
                    }
                  }}
                  className="h-8 text-xs"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addCustom}
                  className="h-8 text-xs"
                >
                  Add
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Role family</Label>
                <Select
                  value={roleFamily}
                  onValueChange={(v) => v !== null && setRoleFamily(v)}
                >
                  <SelectTrigger size="sm" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLE_FAMILIES.filter((f) => f.id !== "all").map((f) => (
                      <SelectItem key={f.id} value={f.id}>
                        {f.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">How long</Label>
                <Select value={weeks} onValueChange={(v) => v !== null && setWeeks(v)}>
                  <SelectTrigger size="sm" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {WEEKS.map((w) => (
                      <SelectItem key={w.value} value={w.value}>
                        {w.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t pt-3">
              <Button variant="outline" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => onGenerate(roleFamily, Number(weeks))}
                disabled={skills.length === 0}
              >
                <Sparkles className="mr-1.5 size-3.5" />
                Plan it
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
