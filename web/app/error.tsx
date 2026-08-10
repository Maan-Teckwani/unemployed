"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";

/**
 * The last resort.
 *
 * Deliberately narrow: a backend that is not running is handled inside each
 * page, because that is a normal state for a tool you start yourself and it
 * deserves a better answer than a full-page error. What lands here is a genuine
 * bug, so the useful things to offer are the digest to report it with and a way
 * back into the app.
 */
export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <div className="max-w-prose space-y-5">
      <div>
        <h1 className="page-title">That did not render</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something in this page threw on the way to the screen. Everything runs
          on your own machine, so nothing left it — and the rest of the app is
          unaffected.
        </p>
      </div>

      <p className="data rounded-md border bg-muted/40 p-3 text-data text-muted-foreground">
        {error.message || "No message"}
        {error.digest && (
          <>
            <br />
            <span className="meta">digest {error.digest}</span>
          </>
        )}
      </p>

      <div className="flex flex-wrap gap-2">
        <Button onClick={unstable_retry}>Try again</Button>
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          Back to home
        </Link>
      </div>
    </div>
  );
}
