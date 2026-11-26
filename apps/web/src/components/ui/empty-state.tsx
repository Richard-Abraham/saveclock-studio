import type { ReactNode } from "react";

import { Card } from "./card";

/** An illustration slot, one sentence and an optional action slot (unused in Phase 1, C2). */
export function EmptyState({
  illustration,
  action,
  children,
}: {
  illustration?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center gap-4 px-4 py-12 text-center">
      {illustration}
      <p className="max-w-[40ch]">{children}</p>
      {action}
    </Card>
  );
}
