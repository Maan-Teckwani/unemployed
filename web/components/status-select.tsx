"use client";

import { useRef } from "react";
import { toast } from "sonner";
import { api, STATUSES, type Status } from "@/lib/api";
import { useStack } from "@/components/stack/stack-provider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** The funnel in the user's words. Order matches STATUSES. */
const LABELS: Record<Status, string> = {
  todo: "To do",
  resume_ready: "Resume ready",
  applied: "Applied",
  outreach_sent: "Outreach sent",
  test: "Test / assessment",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  closed: "Closed",
};

/** Where this job sits in the funnel. Survives re-ingest, so the daily list
 *  shows what is left to do rather than the same jobs every morning. */
export function StatusSelect({
  jobId,
  value,
  onChange,
  className,
}: {
  jobId: number;
  value: Status;
  onChange: (s: Status) => void;
  className?: string;
}) {
  const anchor = useRef<HTMLDivElement>(null);
  const { recordSent } = useStack();

  async function set(next: string | null) {
    if (next === null) return; // the Select can clear itself; a job always has a status
    const status = next as Status;

    // Measured before anything else happens. The optimistic update below can
    // filter this row out of the list entirely, and by the time the request
    // resolves there is nothing left to measure or to throw.
    const from =
      anchor.current?.closest("[data-flip-source]")?.getBoundingClientRect() ??
      anchor.current?.getBoundingClientRect() ??
      null;

    onChange(status); // optimistic: the UI should not wait on a round trip
    recordSent(jobId, status, from);

    try {
      await api.setStatus(jobId, status);
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div ref={anchor}>
      <Select value={value} onValueChange={set}>
        <SelectTrigger className={className ?? "w-40"} size="sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATUSES.map((s) => (
            <SelectItem key={s} value={s}>
              {LABELS[s]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
