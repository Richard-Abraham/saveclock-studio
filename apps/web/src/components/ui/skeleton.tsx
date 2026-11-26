/** Static placeholder block (no shimmer: quiet motion, DESIGN §2.8). Size it with a class. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`rounded-card bg-surface-2 ${className}`} />;
}
