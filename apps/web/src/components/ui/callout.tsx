import type { ComponentProps, ReactNode } from "react";

import { Icon } from "./icons";

export type CalloutVariant = "warn" | "danger";

const VARIANT = {
  warn: { box: "border-warn-ink/30 bg-warn-bg text-warn-ink", icon: "triangle-alert" },
  danger: { box: "border-danger bg-surface text-ink", icon: "circle-alert" },
} as const;

type CalloutProps = {
  variant: CalloutVariant;
  title?: ReactNode;
  /** The message; `id` lands on its paragraph so a Retry button can aria-describe it. */
  children: ReactNode;
  actions?: ReactNode;
} & Pick<ComponentProps<"div">, "id" | "className">;

/** Static notice: no live role (the health indicator is the single live region, AC-S12-3). */
export function Callout({ variant, title, children, actions, id, className = "" }: CalloutProps) {
  const v = VARIANT[variant];
  return (
    <div
      className={`flex flex-col gap-3 rounded-card border p-4 sm:flex-row sm:items-start ${v.box} ${className}`}
    >
      <Icon name={v.icon} className={`mt-1 ${variant === "danger" ? "text-danger" : ""}`} />
      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        <p id={id}>{children}</p>
      </div>
      {actions ? <div className="shrink-0 max-sm:[&>*]:w-full">{actions}</div> : null}
    </div>
  );
}
