import Link from "next/link";

import { Callout } from "@/components/ui";
import { diskFigures } from "@/lib/format";

/** Warn callout at 90 % or more, on S9 and S11 (UX-SPEC owns screens; reviewer decision 7). */
export function DiskWarning({ volume }: { volume: { total: number; free: number } }) {
  const { usedPercent } = diskFigures(volume);
  if (usedPercent < 90) return null;
  return (
    <Callout variant="warn">
      Disk is {usedPercent}% full. Clean up intermediates or delete old projects.{" "}
      <Link href="/settings#storage" className="font-medium underline underline-offset-2">
        Open Settings
      </Link>
    </Callout>
  );
}
