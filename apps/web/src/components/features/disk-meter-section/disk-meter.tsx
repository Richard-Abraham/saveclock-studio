import type { ReactNode } from "react";

import { diskFigures } from "@/lib/format";

/** "3.2 GB of 40 GB used" plus a bar. The figures come from GET /settings, never from markup. */
export function DiskMeter({
  volume,
  trailing,
}: {
  volume: { total: number; free: number };
  /** Inline content after the text on the same line (S9 puts "Manage storage" here). */
  trailing?: ReactNode;
}) {
  const { usedPercent, line } = diskFigures(volume);
  return (
    <div>
      <p className="min-h-11 content-center tabular-nums">
        {line}
        {trailing}
      </p>
      <div
        role="progressbar"
        aria-label="Disk usage"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={usedPercent}
        aria-valuetext={line}
        className="h-2 overflow-hidden rounded-pill bg-surface-2"
      >
        <div className="h-full rounded-pill bg-tick" style={{ width: `${usedPercent}%` }} />
      </div>
    </div>
  );
}
