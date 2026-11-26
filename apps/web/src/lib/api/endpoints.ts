import type { ProjectList, SettingsOut } from "@saveclock/contracts";

import { call, type Api } from "./client";
import { ApiError } from "./errors";

export type HealthState = { kind: "ok" } | { kind: "degraded"; failing: string[] } | { kind: "unreachable" };

/** 200 is ok; a 503 envelope is degraded (naming the failing checks); anything else is unreachable. */
export async function fetchHealth(api: Api): Promise<HealthState> {
  try {
    await call(() => api.GET("/api/v1/health/ready"));
    return { kind: "ok" };
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 503 && cause.enveloped) {
      const checks = cause.details?.["checks"];
      const failing =
        typeof checks === "object" && checks !== null
          ? Object.entries(checks as Record<string, unknown>)
              .filter(([, value]) => value !== "ok")
              .map(([name]) => name)
          : [];
      return { kind: "degraded", failing };
    }
    return { kind: "unreachable" };
  }
}

export function getSettings(api: Api): Promise<SettingsOut> {
  return call(() => api.GET("/api/v1/settings"));
}

export function getProjects(api: Api): Promise<ProjectList> {
  return call(() => api.GET("/api/v1/projects"));
}
