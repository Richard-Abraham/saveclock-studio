import { Skeleton } from "@/components/ui";

/** Loading state of S11: four cards, each a title line and three row lines. */
export function SettingsSkeleton() {
  return (
    <div aria-busy="true" className="mt-6 grid gap-4 lg:grid-cols-2 lg:gap-6">
      <p className="sr-only">Loading settings…</p>
      {Array.from({ length: 4 }, (_, card) => (
        <div key={card} className="flex flex-col gap-3 rounded-card border border-line bg-surface p-4 lg:p-5">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      ))}
    </div>
  );
}
