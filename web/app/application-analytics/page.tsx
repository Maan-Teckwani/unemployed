"use client";

import { useEffect, useState } from "react";
import { api, type ApplicationAnalytics } from "@/lib/api";
import { PageHeader } from "@/components/page-header";

export default function ApplicationAnalyticsPage() {
  const [data, setData] = useState<ApplicationAnalytics | null>(null);
  useEffect(() => { api.applicationAnalytics().then(setData).catch(() => {}); }, []);
  return (
    <div className="space-y-8">
      <PageHeader title="Application analytics" meta="A factual view of your funnel" />
      {!data ? <p className="text-muted-foreground">Loading…</p> : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Sent", data.sent], ["Responses", `${data.response_count} (${Math.round(data.response_rate * 100)}%)`],
          ["Interviews", data.interview_count], ["Offers", `${data.offer_count} (${Math.round(data.conversion_rate * 100)}%)`],
          ["Answer uses", data.answer_uses],
        ].map(([label, value]) => <div key={label} className="rounded-lg border p-4"><p className="meta">{label}</p><p className="data text-2xl">{value}</p></div>)}
      </div>}
    </div>
  );
}
