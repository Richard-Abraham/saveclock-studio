"use client";

import { useEffect, useState } from "react";

import { eventsUrl } from "@/lib/api/driver";

const NAMES = [
  "state",
  "progress",
  "draft_ready",
  "render_ready",
  "mode_a_ready",
  "clip_ready",
  "failed",
] as const;
const TERMINAL = new Set(["failed", "render_ready", "mode_a_ready"]);

export type DriverEvents = {
  /** Plain text lines, newest last. */
  lines: string[];
  /** The latest `ui_status` seen in a `state` event. */
  status: string | null;
  /** Set by `render_ready` / `mode_a_ready`: the files of that render can be downloaded. */
  readyRender: string | null;
  modeAReady: boolean;
};

const EMPTY: DriverEvents = { lines: [], status: null, readyRender: null, modeAReady: false };

function parse(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function line(name: string, data: Record<string, unknown>): string {
  if (name === "progress") return `${String(data.step)} ${String(data.pct)}% ${String(data.message_key)}`;
  if (name === "state") return `status ${String(data.ui_status)}`;
  const rest = Object.entries(data).map(([key, value]) => `${key} ${String(value)}`);
  return [name, ...rest].join(" ");
}

/**
 * The project's server-sent events, read straight from the API origin (OQ-26). The server ends a
 * stream at a terminal event; `reopen` (a counter) opens a new one for the next step.
 */
export function useProjectEvents(projectId: string | null, reopen: number): DriverEvents {
  const [events, setEvents] = useState<DriverEvents>(EMPTY);

  useEffect(() => {
    if (!projectId) return;
    const source = new EventSource(eventsUrl(projectId));
    const onEvent = (event: Event) => {
      const data = parse((event as MessageEvent<string>).data);
      setEvents((prev) => ({
        lines: [...prev.lines.slice(-49), line(event.type, data)],
        status: event.type === "state" ? String(data.ui_status) : prev.status,
        readyRender: typeof data.render_id === "string" ? data.render_id : prev.readyRender,
        modeAReady: prev.modeAReady || event.type === "mode_a_ready",
      }));
      if (TERMINAL.has(event.type)) source.close();
    };
    for (const name of NAMES) source.addEventListener(name, onEvent);
    return () => {
      source.close();
    };
  }, [projectId, reopen]);

  return events;
}
