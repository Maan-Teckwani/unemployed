"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  api,
  REGIONS,
  ROLE_FAMILIES,
  ROLE_FAMILY_GROUPS,
  SENIORITY_LEVELS,
  type Preferences,
} from "@/lib/api";
import { CompanyManager } from "@/components/settings/company-manager";
import { LocationPicker } from "@/components/settings/location-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

const DEFAULTS: Preferences = {
  region: "india",
  max_years: 1,
  allowed_seniority: ["intern", "entry"],
  role_families: ["software", "ai_ml", "data", "devops", "security", "qa"],
  preferred_locations: [],
  remote_ok: true,
};

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-4 accent-foreground"
      />
      {label}
    </label>
  );
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULTS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getPreferences()
      .then((p) => setPrefs({ ...DEFAULTS, ...p }))
      .catch(() => {});
  }, []);

  function setAllFamilies(on: boolean) {
    setPrefs((p) => ({
      ...p,
      role_families: on ? ROLE_FAMILIES.map((f) => f.id) : [],
    }));
  }

  function toggleIn(key: "role_families" | "allowed_seniority", value: string) {
    setPrefs((p) => {
      const list = p[key];
      return {
        ...p,
        [key]: list.includes(value)
          ? list.filter((v) => v !== value)
          : [...list, value],
      };
    });
  }

  async function saveAndRescore() {
    setSaving(true);
    try {
      await api.updatePreferences(prefs);
      const { scored, filtered } = await api.rescore();
      toast.success(`Re-scored: ${scored} scored, ${filtered} filtered out`);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold">Filters</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          What you&apos;re willing to apply to. Filtered jobs aren&apos;t deleted —
          they stay visible behind &ldquo;Show filtered&rdquo; with a reason.
        </p>
      </div>

      <div className="rounded-lg border p-5 space-y-5">
        <div className="space-y-2">
          <Label>Where can you work?</Label>
          <p className="text-xs text-muted-foreground">
            A hard filter: jobs outside this region are dropped at ingestion.
            Remote roles that name no region are always kept.
          </p>
          <Select
            value={prefs.region}
            onValueChange={(v) => setPrefs((p) => ({ ...p, region: v ?? p.region }))}
          >
            <SelectTrigger className="w-72">
              {/* SelectValue renders the raw value unless given a formatter. */}
              <SelectValue>
                {(value) =>
                  REGIONS.find((r) => r.id === value)?.label ?? String(value)
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {REGIONS.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Changing this needs a re-fetch to take full effect — use{" "}
            <strong>Fetch jobs</strong> on the home page.
          </p>
        </div>

        <Separator />

        <div className="space-y-2">
          <div className="flex items-baseline justify-between gap-4">
            <Label>Role families</Label>
            <div className="text-xs space-x-3">
              <button
                type="button"
                className="underline underline-offset-4 hover:text-foreground text-muted-foreground"
                onClick={() => setAllFamilies(true)}
              >
                Select all
              </button>
              <button
                type="button"
                className="underline underline-offset-4 hover:text-foreground text-muted-foreground"
                onClick={() => setAllFamilies(false)}
              >
                Select none
              </button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Every job lands in one of these. Untick a family and its jobs are
            filtered out — even when the title says &ldquo;Engineer&rdquo;.
          </p>
          {ROLE_FAMILY_GROUPS.map((group) => (
            <div key={group} className="pt-1">
              <p className="text-xs font-medium text-muted-foreground">{group}</p>
              <div className="grid grid-cols-2 gap-2 pt-1.5">
                {ROLE_FAMILIES.filter((f) => f.group === group).map((f) => (
                  <Toggle
                    key={f.id}
                    label={f.label}
                    checked={prefs.role_families.includes(f.id)}
                    onChange={() => toggleIn("role_families", f.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        <Separator />

        <div className="space-y-2">
          <Label htmlFor="years">Maximum years of experience required</Label>
          <p className="text-xs text-muted-foreground">
            Jobs asking for more than this are filtered. A fresher wants 0–1.
          </p>
          <Input
            id="years"
            type="number"
            min={0}
            max={10}
            value={prefs.max_years}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, max_years: Number(e.target.value) }))
            }
            className="w-24"
          />
        </div>

        <Separator />

        <div className="space-y-2">
          <Label>Acceptable seniority levels</Label>
          <p className="text-xs text-muted-foreground">
            Only <em>senior</em> and <em>lead</em> are filtered on this label alone —
            a &ldquo;mid&rdquo; guess never overrides the concrete years above,
            because the label is a model judgment and the years are stated fact.
          </p>
          <div className="flex gap-4 pt-1">
            {SENIORITY_LEVELS.map((s) => (
              <Toggle
                key={s}
                label={s}
                checked={prefs.allowed_seniority.includes(s)}
                onChange={() => toggleIn("allowed_seniority", s)}
              />
            ))}
          </div>
        </div>

        <Separator />

        <div className="space-y-2">
          <Label htmlFor="locations">Preferred locations</Label>
          <p className="text-xs text-muted-foreground">
            A <em>soft</em> preference — these rank higher but nothing is filtered
            out, because a great role in another city is still worth seeing.
            Picking from the list matters: boards write &ldquo;Bengaluru&rdquo;
            where you might type &ldquo;Bangalore&rdquo;, and only a known city
            matches both.
          </p>
          <LocationPicker
            region={prefs.region}
            value={prefs.preferred_locations}
            onChange={(next) =>
              setPrefs((p) => ({ ...p, preferred_locations: next }))
            }
          />
          <div className="pt-1">
            <Toggle
              label="Remote roles are fine"
              checked={prefs.remote_ok}
              onChange={(v) => setPrefs((p) => ({ ...p, remote_ok: v }))}
            />
          </div>
        </div>

        <Button onClick={saveAndRescore} disabled={saving}>
          {saving ? "Re-scoring…" : "Save & re-score"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Re-scoring reuses cached extractions, so it takes seconds and makes no
          LLM calls.
        </p>
      </div>

      <CompanyManager />
    </div>
  );
}
