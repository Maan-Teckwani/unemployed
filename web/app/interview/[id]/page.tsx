"use client";

import { use, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type InterviewPrep } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";

export default function InterviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const jobId = Number(id);
  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.getInterviewPrep(jobId).then(setPrep).catch(() => {}); }, [jobId]);

  async function generate() {
    setBusy(true);
    try { setPrep(await api.generateInterviewPrep(jobId)); }
    catch (e) { toast.error(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Interview preparation" meta="Generated only from this job and your verified evidence." />
      <Button onClick={generate} disabled={busy}>{busy ? "Preparing…" : "Generate preparation"}</Button>
      {!prep && <p className="text-sm text-muted-foreground">No preparation saved yet.</p>}
      {prep && <div className="space-y-5">
        {prep.questions.map((q, i) => (
          <section key={i} className="rounded-lg border p-4 space-y-2">
            <h2 className="font-medium">{q.question}</h2>
            <p className="text-sm whitespace-pre-wrap">{q.answer}</p>
            <p className="text-xs text-muted-foreground">Evidence: {q.source_chunk_ids.length ? q.source_chunk_ids.join(", ") : "none — verify before answering"}</p>
          </section>
        ))}
        <section className="rounded-lg border p-4">
          <h2 className="font-medium mb-2">Talking points</h2>
          <ul className="list-disc pl-5 text-sm space-y-1">{prep.talking_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </section>
      </div>}
    </div>
  );
}
