import type { ProjectItem } from "@saveclock/contracts";

import { Card, EmptyState, StatusPill } from "@/components/ui";
import { formatEdited } from "@/lib/format";

import { STATUS_PILL } from "./status";

/** DESIGN's tick glyph: nine ticks, every fourth one tall. Decorative. */
function TickGlyph() {
  return (
    <svg aria-hidden="true" focusable="false" width="72" height="32" viewBox="0 0 72 32">
      {Array.from({ length: 9 }, (_, i) => {
        const tall = i % 4 === 0;
        return (
          <rect
            key={i}
            x={i * 8 + 3}
            y={tall ? 0 : 16}
            width="2"
            height={tall ? 32 : 16}
            rx="1"
            className={tall ? "fill-tick" : "fill-ink-subtle"}
          />
        );
      })}
    </svg>
  );
}

function ProjectRow({ project, now }: { project: ProjectItem; now: Date }) {
  const pill = STATUS_PILL[project.ui_status];
  const title = project.title ?? "Untitled";
  return (
    <Card
      as="li"
      className="grid min-h-16 grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-4 py-3 [contain-intrinsic-size:auto_64px] [content-visibility:auto] lg:grid-cols-[1fr_auto_auto]"
    >
      <span title={title} className="min-w-0 truncate font-semibold">
        {title}
      </span>
      <StatusPill tone={pill.tone} icon={pill.icon}>
        {pill.label}
      </StatusPill>
      <time
        dateTime={project.last_activity_at}
        className="col-span-2 text-small text-ink-subtle lg:col-span-1"
      >
        Edited {formatEdited(project.last_activity_at, now)}
      </time>
    </Card>
  );
}

export function ProjectList({ items, now = new Date() }: { items: ProjectItem[]; now?: Date }) {
  if (items.length === 0) {
    return (
      <EmptyState illustration={<TickGlyph />}>
        No videos yet. Choose a song to make your first one.
      </EmptyState>
    );
  }
  return (
    <ul className="flex flex-col gap-3">
      {items.map((project) => (
        <ProjectRow key={project.id} project={project} now={now} />
      ))}
    </ul>
  );
}
