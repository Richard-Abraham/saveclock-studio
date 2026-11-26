import type { ReactNode } from "react";

import { Card } from "@/components/ui";

/** A titled card. The title is an h2 drawn at the DESIGN h3 step (heading order stays h1 to h2). */
export function SettingsSection({ title, id, children }: { title: string; id: string; children: ReactNode }) {
  return (
    <Card
      as="section"
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex scroll-mt-20 flex-col gap-4 p-4 lg:p-5"
    >
      <h2 id={`${id}-title`} className="font-sans text-h3 font-semibold">
        {title}
      </h2>
      {children}
    </Card>
  );
}

/** One label/value pair of a `<dl>`; extra <dd> lines (help text) go in `help`. */
export function SettingRow({
  label,
  children,
  help,
}: {
  label: string;
  children: ReactNode;
  help?: ReactNode;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[1fr_auto] sm:items-center sm:gap-x-4">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="tabular-nums">{children}</dd>
      {help ? <dd className="text-small text-ink-muted sm:col-span-2">{help}</dd> : null}
    </div>
  );
}
