import { Skeleton } from "@/components/ui";

/** Loading state of S9: the disk line and bar plus six rows, all static blocks. */
export function ProjectsSkeleton() {
  return (
    <div aria-busy="true" className="mt-4 flex flex-col gap-6">
      <p className="sr-only">Loading projects…</p>
      <div className="flex flex-col gap-3 lg:max-w-[calc((100%-2rem)/3)]">
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-2 w-full" />
      </div>
      <div className="flex flex-col gap-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
    </div>
  );
}
