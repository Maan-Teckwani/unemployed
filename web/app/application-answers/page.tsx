"use client";

import { useEffect, useState } from "react";
import { api, type ApplicationAnswer } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";

export default function ApplicationAnswersPage() {
  const [answers, setAnswers] = useState<ApplicationAnswer[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [approved, setApproved] = useState(false);
  const load = () => api.listApplicationAnswers().then(setAnswers).catch(() => {});
  useEffect(() => { load(); }, []);
  async function save() {
    if (!question.trim() || !answer.trim()) return;
    await api.createApplicationAnswer({
      question, answer, category: "general", is_sensitive: false, explicit_approval: approved,
    });
    setQuestion(""); setAnswer(""); setApproved(false); load();
  }
  return (
    <div className="space-y-8">
      <PageHeader title="Application answers" meta="Your approved, reusable answers" />
      <section className="space-y-3 rounded-lg border p-4">
        <input className="w-full rounded border p-2" placeholder="Question" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <textarea className="w-full rounded border p-2" placeholder="Answer" value={answer} onChange={(e) => setAnswer(e.target.value)} rows={4} />
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} /> I approve saving this answer</label>
        <Button onClick={save}>Save answer</Button>
      </section>
      <div className="space-y-3">{answers.map((item) => <article key={item.id} className="rounded-lg border p-4"><h2 className="font-medium">{item.question}</h2><p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{item.answer}</p><p className="meta mt-2">{item.use_count} uses{item.is_sensitive ? " · sensitive · approved" : ""}</p></article>)}</div>
    </div>
  );
}
