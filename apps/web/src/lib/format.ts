/** The one place numbers and dates become text (DESIGN §7, UX-SPEC S9). */

const GB = 1e9;
const NBSP = " ";
const MS_PER_DAY = 86_400_000;

const oneDecimal = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });
const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const absolute = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** Decimal GB, one decimal at most, no trailing ".0": 3.2 -> "3.2 GB", 40 -> "40 GB". */
export function formatGB(bytes: number): string {
  return `${oneDecimal.format(bytes / GB)}${NBSP}GB`;
}

export type DiskFigures = { usedPercent: number; usedBytes: number; totalBytes: number; line: string };

/** Used = total minus free. The percent is floored so "90%" never shows below the threshold. */
export function diskFigures(volume: { total: number; free: number }): DiskFigures {
  const usedBytes = Math.max(0, volume.total - volume.free);
  const usedPercent = volume.total > 0 ? Math.min(100, Math.floor((usedBytes / volume.total) * 100)) : 0;
  return {
    usedPercent,
    usedBytes,
    totalBytes: volume.total,
    line: `${formatGB(usedBytes)} of ${formatGB(volume.total)} used`,
  };
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** "today", "yesterday", "3 days ago" up to 30 days, then "12 Nov 2026". */
export function formatEdited(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(then)) / MS_PER_DAY);
  if (days >= 0 && days <= 30) return relative.format(-days, "day");
  return absolute.format(then);
}
