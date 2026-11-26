"use client";

import { StatusPill } from "@/components/ui";

import { useHealth } from "./use-health";

/** Says in words whether the API can be reached and which check fails. The single live region. */
export function HealthIndicator() {
  const { data } = useHealth();
  return (
    <div aria-live="polite" aria-atomic="true" className="ml-auto">
      {data === undefined ? (
        <StatusPill tone="neutral" icon="clock">
          Checking server…
        </StatusPill>
      ) : data.kind === "ok" ? (
        <StatusPill tone="lock" icon="check">
          Server ok
        </StatusPill>
      ) : data.kind === "degraded" ? (
        <StatusPill tone="warn" icon="triangle-alert">
          Server degraded
          {data.failing.length > 0 ? (
            <>
              : <span translate="no">{data.failing.join(", ")}</span>
            </>
          ) : null}
        </StatusPill>
      ) : (
        <StatusPill tone="danger" icon="circle-alert">
          Server unreachable
        </StatusPill>
      )}
    </div>
  );
}
