"use client";

import Link from "next/link";
import { useStack } from "@/components/stack/stack-provider";
import { Odometer } from "@/components/stack/odometer";

/**
 * The pile, shrunk to fit in the nav.
 *
 * It is here on every page for two reasons: so the number is visible from
 * wherever you happen to be working, and so a card thrown from the ranked list
 * has something to land on that will still exist after you navigate.
 *
 * Three lines of paper rather than an icon — at this size the pile is only
 * legible as itself, and a generic glyph would say nothing the number doesn't.
 */
export function StackPip() {
  const { model, counts, pipRef } = useStack();

  // Prefer the server's count until the applications list has loaded, so the
  // number does not start at zero and jump.
  const total = model.total || counts?.pile || 0;
  const live = model.byState.test + model.byState.interview + model.byState.offer;

  return (
    <Link
      href="/"
      ref={pipRef as React.Ref<HTMLAnchorElement>}
      title={live > 0 ? `${total} sent · ${live} in progress` : `${total} sent`}
      className="group/pip data-[just-landed]:border-foreground flex items-center gap-1.5 rounded-md border border-transparent px-1.5 py-1 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <span aria-hidden className="flex w-3 flex-col justify-end gap-[2px]">
        <span className="h-px w-full bg-paper-edge" />
        <span className="h-px w-full bg-paper-edge" />
        <span
          className={`h-[2px] w-full ${
            model.byState.offer > 0
              ? "bg-state-offer"
              : model.byState.interview > 0
                ? "bg-state-interview"
                : "bg-foreground/70"
          }`}
        />
      </span>
      <Odometer value={total} className="data text-data font-medium" />
      <span className="sr-only">
        applications sent{live > 0 ? `, ${live} still in progress` : ""}
      </span>
    </Link>
  );
}
