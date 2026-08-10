import { Skeleton } from "@/components/ui/skeleton";

/** The pile and the checklist, before either has anything to say. */
export function HomeSkeleton() {
  return (
    <div className="space-y-10" role="status" aria-label="Loading">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-6">
        <Skeleton className="h-[334px] w-[252px] shrink-0 rounded-md" />
        <div className="min-w-0 flex-1 space-y-3 pb-1">
          <Skeleton className="h-14 w-40" />
          <Skeleton className="h-3.5 w-56" />
          <Skeleton className="h-3.5 w-full max-w-prose" />
        </div>
      </div>
      <div className="rounded-lg border divide-y">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3.5">
            <Skeleton className="size-5 shrink-0 rounded-full" />
            <Skeleton className="h-3.5 w-48" />
          </div>
        ))}
      </div>
    </div>
  );
}
