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
            {s.rewritten ? " · rewritten" : " · kept unchanged"}
          </Badge>
        ))}
      </div>

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
