"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { copy } from "@/lib/copy";

/**
 * The one time we ask someone who joined under the old promise.
 *
 * Everyone on the wall before there was an email column signed up under copy
 * that said their address was not stored. That changed, and the honest way to
 * change it is to say so to their face rather than to take the address quietly
 * on their next sign-in, which is what the code used to do.
 *
 * Both buttons are the same size and neither is disabled. "No thanks" writes a
 * row too, recording that the question was asked, so declining is a real answer
 * that sticks rather than a delay before being asked again.
 *
 * A failed write leaves them here with a message. It does not fall through to
 * the install steps, because a silent failure here means the next visit asks
 * again, and being asked twice looks like the answer was ignored.
 */
export function EmailConsent() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function answer(keep: boolean) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/signups/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // No address in the body. The server takes it off the session.
        body: JSON.stringify({ keep }),
      });
      if (!res.ok) {
        setError(copy.auth.consentFailed);
        return;
      }
      // Where they were going before this stopped them.
      router.push("/#install");
      router.refresh();
    } catch {
      setError(copy.auth.consentFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border p-6">
      <p className="text-sm leading-relaxed">{copy.auth.consentDetail}</p>

      {error && (
        <p className="mt-4 rounded-md border px-3 py-2 text-sm font-medium" role="alert">
          {error}
        </p>
      )}

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => answer(true)}
          disabled={busy}
          className="border-foreground bg-foreground text-background rounded-lg border px-4 py-2 text-sm font-medium focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-40"
        >
          {copy.auth.consentAccept}
        </button>
        <button
          type="button"
          onClick={() => answer(false)}
          disabled={busy}
          className="hover:bg-muted rounded-lg border px-4 py-2 text-sm font-medium focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-40"
        >
          {copy.auth.consentDecline}
        </button>
      </div>
    </div>
  );
}
