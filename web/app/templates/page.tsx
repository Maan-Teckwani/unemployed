"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type ResumeTemplate } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

/**
 * Paste your Overleaf resume once; every tailored resume comes back in it.
 *
 * The detected-sections list is the whole point of showing anything after a
 * save: heading names differ between templates, and finding out here that
 * "Relevant Experience" was recognised beats discovering it after a generation
 * that changed nothing.
 */
export default function TemplatesPage() {
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);
  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setTemplates(await api.listTemplates());
    } catch {
      // Backend not reachable yet.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function save() {
    setSaving(true);
    try {
      const created = await api.createTemplate(name, source);
      const usable = created.sections.filter((s) => s.rewritable).length;
      toast.success(
        usable > 0
          ? `Saved — ${usable} section${usable === 1 ? "" : "s"} can be tailored`
          : "Saved, but no section was recognised — check the headings below",
      );
      setName("");
      setSource("");
      refresh();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function remove(template: ResumeTemplate) {
    if (!confirm(`Delete "${template.name}"?`)) return;
    try {
      await api.deleteTemplate(template.id);
      refresh();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Resume templates</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Paste the LaTeX from Overleaf. Tailored resumes then come back in your
          own format, and only the wording inside Experience, Projects,
          Certifications and Skills is ever rewritten — your preamble, macros and
          layout are copied through untouched.
        </p>
      </div>

      <div className="rounded-lg border p-5 space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Overleaf resume"
            className="max-w-sm"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="source">LaTeX source</Label>
          <textarea
            id="source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            rows={14}
            spellCheck={false}
            placeholder={"\\documentclass[letterpaper,11pt]{article}\n…"}
            className="w-full rounded-md border bg-transparent p-3 font-mono text-xs focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>

        <Button onClick={save} disabled={saving || source.trim().length < 20}>
          {saving ? "Saving…" : "Save template"}
        </Button>
      </div>

      <Separator />

      <div className="space-y-3">
        <h2 className="font-medium">Saved templates</h2>
        {templates.length === 0 && (
          <p className="text-sm text-muted-foreground">
            None yet. Until you add one, resumes are generated into the built-in
            ATS-safe PDF layout.
          </p>
        )}
        {templates.map((t) => (
          <div key={t.id} className="rounded-lg border p-4 space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium">{t.name}</span>
              {t.is_default && <Badge variant="secondary">default</Badge>}
              <span className="flex-1" />
              {!t.is_default && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    api
                      .setDefaultTemplate(t.id)
                      .then(refresh)
                      .catch((e) => toast.error(String(e)))
                  }
                >
                  Use this one
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => remove(t)}>
                Delete
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {t.sections.map((s, i) => (
                <Badge key={i} variant={s.rewritable ? "secondary" : "outline"}>
                  {s.heading}
                  {!s.rewritable && " · kept as is"}
                </Badge>
              ))}
              {t.sections.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No \section{"{…}"} headings found — this template cannot be
                  tailored.
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
