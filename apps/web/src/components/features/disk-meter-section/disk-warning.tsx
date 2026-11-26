import Link from "next/link";

import { Callout } from "@/components/ui";
import { diskFigures } from "@/lib/format";

/**
 * Warn callout at 90 % or more, on S9 and S11 (UX-SPEC owns screens; reviewer decision 7). On S11
 * (`link={false}`) it would only link to the page you are on, so it is left out there.
 */
export function DiskWarning({
  volume,
  link = true,
}: {
  volume: { total: number; free: number };
  link?: boolean;
}) {
  const { usedPercent } = diskFigures(volume);
  if (usedPercent < 90) return null;
  return (
    <Callout variant="warn">
      Disk is {usedPercent}% full. Clean up intermediates or delete old projects.
      {link ? (
        <>
          {" "}
          <Link href="/settings#storage" className="link-warn font-medium">
            Open Settings
          </Link>
        </>
      ) : null}
    </Callout>
  );
}
