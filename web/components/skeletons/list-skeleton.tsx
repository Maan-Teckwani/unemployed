import { Skeleton } from "@/components/ui/skeleton";

/**
 * The waiting state for any of the bordered lists.
 *
 * Shared between a route's `loading.tsx` and the page's own pending branch on
 * purpose: they are two different waits — the JavaScript arriving, then the
 * data — and if they looked different the handover would flicker for no reason
 * the user could name.
 */
export function ListSkeleton({ rows = 6, title = true }: { rows?: number; title?: boolean }) {
  return (
    <div className="space-y-6">
      {title && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-3.5 w-40" />
        </div>
      )}
      <div className="rounded-lg border divide-y" role="status" aria-label="Loading">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3.5">
            <Skeleton className="h-6 w-8 shrink-0" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-3.5 w-2/5" />
              <Skeleton className="h-3 w-1/4" />
            </div>
            <Skeleton className="h-7 w-32 shrink-0" />
          </div>
        ))}
      </div>
    </div>
  );
}
