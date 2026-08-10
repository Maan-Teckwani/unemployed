"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState, ViewTransition } from "react";
import { toast } from "sonner";
import {
  api,
  type JobDetail,
  type MatchDetail,
  type Resume,
  type Status,
} from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { recall } from "@/lib/job-cache";
import { scoreTone } from "@/lib/score";
import { FitBreakdown } from "@/components/matches/fit-breakdown";
import { JobDetailSkeleton } from "@/components/skeletons/job-detail-skeleton";
import { OutreachPanel } from "@/components/outreach/outreach-panel";
import { ProjectPanel } from "@/components/projects/project-panel";
import { LatexPanel } from "@/components/resume/latex-panel";
import { ResumeEditor } from "@/components/resume/resume-editor";
import { useStack } from "@/components/stack/stack-provider";
import { StatusSelect } from "@/components/status-select";
import { Working } from "@/components/working";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const jobId = Number(id);

  const [job, setJob] = useState<JobDetail | null>(null);
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const [generating, setGenerating] = useState(false);
  const [showSource, setShowSource] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>("todo");
  const [editing, setEditing] = useState(false);
  const [hasTemplate, setHasTemplate] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const { model } = useStack();
  const inPile = model.sheets.some((s) => s.jobId === jobId);

  const load = useCallback(async () => {
    try {
      const [j, m, r, apps, templates] = await Promise.all([
        api.getJob(jobId),
        // A job may never have been scored (e.g. just added manually).
        api.matchDetail(jobId).catch(() => null),
        api.resumeForJob(jobId).catch(() => null),
        api.listApplications().catch(() => []),
        api.listTemplates().catch(() => []),
      ]);
      setJob(j);
      setMatch(m);
      setResume(r);
      setHasTemplate(templates.some((t) => t.is_default));
      setStatus(apps.find((a) => a.job_id === jobId)?.status ?? "todo");
    } catch (e) {
      // Only `getJob` can reach here — the other four swallow their own errors
      // because a job with no score, no resume and no template is still a job
      // worth showing. Recording the reason matters because this page renders a
      // skeleton until `job` arrives: swallowed, a job that no longer exists
      // left the skeleton up forever, which reads as a hang rather than as an
      // answer. A stale link from Apply today is the normal way to get one.
      setFailed(String(e));
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  async function generate() {
    setGenerating(true);
    try {
      // Your own template wins when you have one; otherwise the built-in PDF.
      setResume(await api.generateResume(jobId, hasTemplate ? "latex" : "pdf"));
      // Generating is what makes a job "ready to send", so reflect that.
      setStatus("resume_ready");
      api.setStatus(jobId, "resume_ready").catch(() => {});
      toast.success("Resume generated");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setGenerating(false);
    }
  }

  if (failed)
    return (
      <div className="max-w-prose space-y-4">
        <h1 className="page-title">This job is not here</h1>
        <p className="text-muted-foreground text-sm">
          {failed.includes("404")
            ? "It was removed the last time the boards were fetched — a company takes a posting down and the next fetch marks it gone. The list on Apply today is current."
            : `Could not load it: ${failed}`}
        </p>
        {/* Arriving from a sheet in the pile is the common way to land here: a
            posting you applied to weeks ago is exactly the kind that gets taken
            down. The count must not look like a mistake. */}
        {inPile && failed.includes("404") && (
          <p className="text-muted-foreground text-sm">
            You applied to this one, and it still counts. A posting coming down
            does not un-send an application, so it keeps its place in your pile.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Link
            href="/today"
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            Back to Apply today
          </Link>
          {inPile && (
            <Link href="/" className={buttonVariants({ variant: "outline", size: "sm" })}>
              Back to your pile
            </Link>
          )}
        </div>
      </div>
    );

  // What the ranked list already knew, so the header is on screen in the first
  // frame instead of behind a skeleton — and so the title exists at the moment
  // of the transition, which is what lets it morph rather than cut.
  const known = job ?? recall(jobId);

  if (!known) return <JobDetailSkeleton />;

  const ats = resume?.ats_report;
  const sections = ["Experience", "Projects", "Achievements"];

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/today"
          className="meta normal-case tracking-normal underline underline-offset-4 hover:text-foreground"
        >
          ← Back to Apply today
        </Link>
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <ViewTransition name={`job-${jobId}`}>
            <h1 className="page-title">{known.title}</h1>
          </ViewTransition>
          {match && (
            <span
              className={`data text-display-md ${scoreTone(match.score)}`}
              title="Fit score out of 100"
            >
              {Math.round(match.score * 100)}
            </span>
          )}
          {match?.tier === "estimated" && (
            <Badge
              variant="outline"
              title="Ranked on semantic + keyword fit; required skills not yet extracted."
            >
              estimated
            </Badge>
          )}
          {match?.hard_filtered && (
            <Badge variant="outline">filtered: {match.filter_reason}</Badge>
          )}
        </div>
        <p className="meta mt-1.5 normal-case tracking-normal">
          {known.company} · {known.location || "—"}
          {job && ` · ${job.source}`}
          {known.remote && <Badge variant="secondary" className="ml-2">remote</Badge>}
        </p>
      </div>

      {match && <FitBreakdown match={match} />}

      {/* Sticky: on a long job page the resume pushes these off screen, and
          "Apply" and the status control are exactly what you reach for last. */}
      <div className="sticky top-0 z-10 -mx-2 flex flex-wrap items-center gap-3 border-b bg-background px-2 py-3">
        <Button onClick={generate} disabled={generating}>
          {generating
            ? "Generating…"
            : hasTemplate
              ? "Generate resume in my LaTeX"
              : "Generate tailored resume"}
        </Button>
        {resume && !resume.latex && (
          <Button
            variant="outline"
            onClick={() =>
              downloadFile(api.resumePdfUrl(resume.id), `resume_${resume.id}.pdf`)
            }
          >
            Download PDF
          </Button>
        )}
        {resume && !resume.latex && (
          <Button variant="outline" onClick={() => setEditing((v) => !v)}>
            {editing ? "Close editor" : "Edit"}
          </Button>
        )}
        {/* The apply link is the one thing the cached summary does not carry,
            so until the full record lands this is a disabled placeholder rather
            than a link to nowhere. */}
        {job ? (
          <Button
            variant="outline"
            nativeButton={false}
            render={<a href={job.apply_url} target="_blank" rel="noopener noreferrer" />}
          >
            Open application
          </Button>
        ) : (
          <Button variant="outline" disabled>
            Open application
          </Button>
        )}
        <StatusSelect jobId={jobId} value={status} onChange={setStatus} />
      </div>

      {generating && (
        <Working
          label={
            hasTemplate
              ? "Rewriting your template, one section at a time (~40s each)"
              : "Reading your knowledge base and writing bullets (~40s)"
          }
        />
      )}

      {resume && editing && (
        <ResumeEditor
          resume={resume}
          onSaved={(r) => {
            setResume(r);
            setEditing(false);
          }}
        />
      )}

      {resume?.latex && <LatexPanel resume={resume} />}

      {resume && !resume.latex && ats && (
        <div className="rounded-lg border p-4 space-y-2">
          <h2 className="font-medium text-sm">ATS check</h2>
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant={ats.parse_ok ? "secondary" : "destructive"}>
              {ats.parse_ok ? "Parses cleanly" : "Parse issues"}
            </Badge>
            <Badge variant="outline">{ats.page_count} page</Badge>
            {ats.coverage !== null && (
              <Badge variant="outline">
                Keyword coverage {Math.round(ats.coverage * 100)}%
              </Badge>
            )}
          </div>
          {ats.required_missing?.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Not evidenced in your KB (never faked):{" "}
              {ats.required_missing.join(", ")}
            </p>
          )}
          {ats.warnings?.map((w) => (
            <p key={w} className="text-xs text-amber-600 dark:text-amber-500">
              ⚠ {w}
            </p>
          ))}
          {ats.rejected_bullets?.length > 0 && (
            <div className="text-xs space-y-1 pt-1">
              <p className="text-muted-foreground">
                Rejected by truthfulness validation:
              </p>
              {ats.rejected_bullets.map((r, i) => (
                <p key={i} className="text-muted-foreground">
                  ✕ {r.text.slice(0, 80)} — <em>{r.reason}</em>
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {resume && !resume.latex && (
        <div className="space-y-4">
          <Separator />
          <div>
            <h2 className="font-medium">Skills</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {resume.skills.join(" · ")}
            </p>
          </div>

          {sections.map((section) => {
            const items = resume.bullets.filter((b) => b.section === section);
            if (items.length === 0) return null;
            return (
              <div key={section} className="space-y-2">
                <h2 className="font-medium">{section}</h2>
                {items.map((b, i) => (
                  <div key={i} className="text-sm">
                    <p>• {b.text}</p>
                    <button
                      onClick={() =>
                        setShowSource(
                          showSource === b.source_chunk_ids[0]
                            ? null
                            : b.source_chunk_ids[0],
                        )
                      }
                      className="text-xs text-muted-foreground underline mt-0.5"
                    >
                      from: {b.title}
                    </button>
                    {showSource === b.source_chunk_ids[0] && (
                      <p className="text-xs text-muted-foreground border-l-2 pl-2 mt-1">
                        {resume.sources[String(b.source_chunk_ids[0])]?.accomplishment}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}

      <Separator />
      <ProjectPanel jobId={jobId} />

      <Separator />
      <OutreachPanel jobId={jobId} />

      {job && (
        <>
          <Separator />
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              Job description
            </summary>
            <pre className="mt-2 text-xs text-muted-foreground whitespace-pre-wrap">
              {job.description.slice(0, 4000)}
            </pre>
          </details>
        </>
      )}
    </div>
  );
}
