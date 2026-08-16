"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { api, type ChunkIn, type ParseJob } from "@/lib/api";
import { ChunkEditor, type EditableChunk } from "@/components/kb/chunk-editor";
import { GoBackTo } from "@/components/go-back-to";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const KINDS = [
  "resume",
  "projects",
  "achievements",
  "leadership",
  "skills",
  "non-technical skills",
  "certifications",
  "other",
];

type Upload = { file: File; kind: string };

function toEditable(c: ChunkIn): EditableChunk {
  return {
    type: c.type,
    title: c.title,
    context: c.context ?? "",
    company: c.company ?? "",
    date_range: c.date_range ?? "",
    accomplishment: c.accomplishment,
    technologies: c.technologies.join(", "),
    skills: c.skills.join(", "),
    impact: c.impact ?? "",
  };
}

function csv(s: string): string[] {
  return s.split(",").map((x) => x.trim()).filter(Boolean);
}

function toChunkIn(e: EditableChunk): ChunkIn {
  return {
    type: e.type,
    title: e.title.trim() || "Untitled",
    context: e.context.trim() || null,
    company: e.company.trim() || null,
    date_range: e.date_range.trim() || null,
    accomplishment: e.accomplishment.trim(),
    technologies: csv(e.technologies),
    skills: csv(e.skills),
    impact: e.impact.trim() || null,
  };
}

export default function ImportPage() {
  const router = useRouter();
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [proposed, setProposed] = useState<EditableChunk[] | null>(null);
  const [parsing, setParsing] = useState(false);
  const [job, setJob] = useState<ParseJob | null>(null);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  function onFiles(list: FileList | null) {
    if (!list) return;
    setUploads(Array.from(list).map((file) => ({ file, kind: "resume" })));
    setProposed(null);
    setErrors([]);
  }

  /**
   * Start the parse, then poll it to the end.
   *
   * No timeout anywhere in this path: a long CV is many model calls on your own
   * machine, and the honest thing to do is show how far along it is rather than
   * give up on it. Every second of that wait is a section being read.
   */
  async function parse() {
    if (uploads.length === 0) return toast.error("Choose at least one file");
    setParsing(true);
    setJob(null);
    setErrors([]);
    try {
      let current = await api.startParse(uploads);
      setJob(current);

      while (current.status === "running") {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          current = await api.parseStatus(current.id);
        } catch (e) {
          // A parse job lives in the backend's memory, not a table (see
          // app/api/parse_jobs.py), so a restart loses it — and the backend runs
          // under --reload, which restarts on every edit to it. "404 Not Found:
          // parse job not found" is not something a user can act on; the actual
          // situation is, and the recovery is one click.
          throw String(e).includes("404")
            ? new Error("The backend restarted while this was reading. Parse the files again.")
            : e;
        }
        setJob(current);
      }

      if (current.status === "failed") throw new Error(current.message);
      setErrors(current.errors);

      setProposed(current.chunks.map(toEditable));
      if (current.chunks.length === 0)
        toast.message("No accomplishments found — try another file.");
      else toast.success(`Parsed ${current.chunks.length} chunk(s) — review below`);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setParsing(false);
    }
  }

  function patch(i: number, p: Partial<EditableChunk>) {
    setProposed((prev) =>
      prev ? prev.map((c, idx) => (idx === i ? { ...c, ...p } : c)) : prev,
    );
  }

  async function saveAll() {
    if (!proposed) return;
    const valid = proposed.filter((c) => c.accomplishment.trim());
    if (valid.length === 0) return toast.error("Nothing to save");
    setSaving(true);
    try {
      await api.saveChunks(valid.map(toChunkIn));
      toast.success(`Saved ${valid.length} chunk(s) to your Knowledge Base`);
      router.push("/kb");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Import from documents</h1>
        <p className="text-muted-foreground mt-1 max-w-prose">
          Upload your resume and any documents about projects, achievements,
          leadership, or skills. They&apos;re parsed into chunks you can review
          and edit before saving — nothing is saved until you say so.
        </p>
      </div>

      <div className="rounded-lg border p-5 space-y-4">
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md"
          onChange={(e) => onFiles(e.target.files)}
          className="block text-sm file:mr-3 file:rounded-md file:border file:px-3 file:py-1.5 file:text-sm file:bg-muted"
        />

        {uploads.length > 0 && (
          <div className="space-y-2">
            {uploads.map((u, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className="truncate flex-1">{u.file.name}</span>
                <Select
                  value={u.kind}
                  onValueChange={(v) =>
                    setUploads((prev) =>
                      prev.map((x, idx) =>
                        idx === i ? { ...x, kind: v ?? x.kind } : x,
                      ),
                    )
                  }
                >
                  <SelectTrigger className="w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {KINDS.map((k) => (
                      <SelectItem key={k} value={k}>
                        {k}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        )}

        <Button onClick={parse} disabled={parsing || uploads.length === 0}>
          {parsing ? "Reading…" : "Parse documents"}
        </Button>

        {job && parsing && (
          <div className="space-y-1.5">
            <ProgressBar done={job.done} total={job.total} message={job.message} />
            <p className="text-xs text-muted-foreground">
              Your local model reads each section in full — a long CV can take
              several minutes. Nothing is saved until you review it.
            </p>
            <GoBackTo />
          </div>
        )}

        {errors.length > 0 && (
          <div className="rounded-md bg-destructive/10 text-destructive dark:bg-destructive/20 p-3 space-y-1 text-sm">
            {errors.map((error, i) => (
              <p key={i}>{error}</p>
            ))}
          </div>
        )}
      </div>

      {proposed && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Review proposed chunks ({proposed.length})</h2>
            <Button onClick={saveAll} disabled={saving}>
              {saving ? "Saving…" : "Save all to Knowledge Base"}
            </Button>
          </div>
          {proposed.map((c, i) => (
            <ChunkEditor
              key={i}
              value={c}
              onChange={(p) => patch(i, p)}
              onRemove={() =>
                setProposed((prev) => prev!.filter((_, idx) => idx !== i))
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
