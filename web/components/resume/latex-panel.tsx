"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api, type Resume } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * The tailored document, in the user's own format.
 *
 * "Open in Overleaf" is a plain cross-origin form POST to /docs with the source
 * in `snip` — Overleaf's documented way in, needing no API key and no hosting.
 * It is a form rather than a fetch because the response is a page for the user,
 * not data for us.
 */
export function LatexPanel({ resume }: { resume: Resume }) {
  const [open, setOpen] = useState(false);
  const sections = resume.ats_report.latex_sections ?? [];
  const chosen = sections.filter((s) => s.mode === "entries" && s.rewritten);
  const declined = sections.filter((s) => s.entries_declined);

  async function copy() {
    try {
      await navigator.clipboard.writeText(resume.latex);
      toast.success("LaTeX copied");
    } catch {
      toast.error("Could not copy — select the text and copy manually");
    }
  }

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="font-medium text-sm">Your LaTeX resume</h2>
        {sections.map((s) => (
          <Badge
            key={s.heading}
            variant={s.rewritten ? "secondary" : "outline"}
            title={s.reason}
          >
            {s.heading}
            {!s.rewritten
              ? " · kept unchanged"
              : s.mode === "entries"
                ? " · projects chosen"
                : " · rewritten"}
          </Badge>
        ))}
      </div>

      {/* Which projects are on the page, when they were chosen rather than
          reworded. Without this the swap is invisible: the document looks like
          the one that was uploaded until you read it line by line. */}
      {chosen.map((s) => (
        <div key={s.heading} className="rounded-md border bg-muted/20 p-3 space-y-2">
          <p className="text-xs font-medium">
            {s.heading}: picked from your knowledge base for this job
          </p>
          <ul className="space-y-1">
            {(s.entries ?? []).map((e, i) => (
              <li key={`${e.title}-${i}`} className="text-xs">
                <span className="font-medium">{e.title}</span>
                <span className="text-muted-foreground">
                  {" "}
                  · {e.bullets.length} bullet{e.bullets.length === 1 ? "" : "s"}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            {s.chosen_by === "ranking"
              ? "Chosen by relevance to this job, quoting your knowledge base word for word. Your local model could not produce a valid selection, so nothing here was rewritten."
              : "Chosen and reworded for this job. Every number and name traces back to an accomplishment you wrote."}
          </p>
        </div>
      ))}

      {/* Why a section was only reworded. Without this the answer to "why
          didn't it pick my projects" is invisible, and the fix is usually one
          line of the user's own template. */}
      {declined.map((s) => (
        <p key={s.heading} className="text-xs text-muted-foreground">
          <span className="font-medium">{s.heading}:</span> reworded the entries
          you wrote rather than choosing new ones, because{" "}
          {s.entries_declined}.
        </p>
      ))}

      {sections.some((s) => !s.rewritten) && (
        <p className="text-xs text-muted-foreground">
          A section is kept exactly as you wrote it whenever the rewrite failed
          validation — a slightly less tailored resume beats one that will not
          compile or claims something you cannot back up.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <form
          action="https://www.overleaf.com/docs"
          method="post"
          target="_blank"
          rel="noopener noreferrer"
        >
          <input type="hidden" name="snip" value={resume.latex} />
          <input type="hidden" name="engine" value="pdflatex" />
          <Button type="submit">Open in Overleaf</Button>
        </form>
        <Button variant="outline" onClick={copy}>
          Copy LaTeX
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            downloadFile(api.resumeLatexUrl(resume.id), `resume_${resume.id}.tex`)
          }
        >
          Download .tex
        </Button>
        <Button variant="outline" onClick={() => setOpen((v) => !v)}>
          {open ? "Hide source" : "Show source"}
        </Button>
      </div>

      {open && (
        <pre className="max-h-96 overflow-auto rounded-md border bg-muted/30 p-3 text-xs whitespace-pre-wrap">
          {resume.latex}
        </pre>
      )}
    </div>
  );
}
