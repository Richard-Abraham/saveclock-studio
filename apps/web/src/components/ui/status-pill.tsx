import type { ReactNode } from "react";

import { Icon, type IconName } from "./icons";

export type PillTone = "neutral" | "lock" | "warn" | "danger";

const TONE: Record<PillTone, { box: string; icon: string }> = {
  neutral: { box: "bg-surface-2 text-ink", icon: "text-ink-muted" },
  lock: { box: "bg-surface-2 text-ink", icon: "text-lock" },
  warn: { box: "bg-warn-bg text-warn-ink", icon: "" },
  danger: { box: "bg-surface-2 text-ink", icon: "text-danger" },
};

/** Status as text plus icon, never colour alone. */
export function StatusPill({
  tone,
  icon,
  children,
}: {
  tone: PillTone;
  icon: IconName;
  children: ReactNode;
}) {
  const t = TONE[tone];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-pill px-3 py-1 text-small font-medium whitespace-nowrap ${t.box}`}
    >
      <Icon name={icon} className={`size-4 ${t.icon}`} />
      <span>{children}</span>
    </span>
  );
}
