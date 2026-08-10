import { Skeleton, SkeletonRows } from "@/components/ui/skeleton";

/** One job, before it has loaded. */
export function JobDetailSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading">
      <div className="space-y-3">
        <Skeleton className="h-3.5 w-36" />
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
      </div>
      <Skeleton className="h-11 w-full rounded-lg" />
      <SkeletonRows rows={3} />
    </div>
  );
}
