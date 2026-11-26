import type { ErrorEnvelope, HealthReady, ProjectItem, ProjectList, SettingsOut } from "@saveclock/contracts";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

/** The API as the server components see it (the default API_INTERNAL_URL origin). */
export const API = "http://api:8000";
/** The API as the browser sees it through the rewrite (the test's browser client base URL). */
export const WEB = "http://localhost:3000";

export const server = setupServer();

export function settingsFixture(overrides: Partial<SettingsOut> = {}): SettingsOut {
  return {
    keys: {
      pexels: { configured: true },
      pixabay: { configured: false },
      anthropic: { configured: false, llm_enabled: false, fallback_active: true },
    },
    stock: { pixabay_enabled: false },
    tuning: {
      heavy: 2,
      torch_threads: 6,
      ffmpeg_threads: 6,
      fetch_concurrency: 4,
      device: "cpu",
      source: { heavy: "auto" },
    },
    disk: {
      volume: { total: 40e9, free: 36.8e9 },
      by_area: { songs: 0, work: 0, renders: 0 },
      projects: [],
    },
    intermediate_ttl_days: 7,
    ...overrides,
  };
}

export function projectFixture(overrides: Partial<ProjectItem> = {}): ProjectItem {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    title: "night_drive_final",
    ui_status: "draft",
    disk_bytes: 0,
    last_activity_at: "2026-11-26T10:00:00Z",
    created_at: "2026-11-26T09:00:00Z",
    ...overrides,
  };
}

export function envelope(
  code: ErrorEnvelope["error"]["code"],
  details: Record<string, unknown> | null = null,
): ErrorEnvelope {
  return { error: { code, message: "x", details, request_id: "abc", doc_url: null } };
}

export const json = {
  settings: (body: SettingsOut) => HttpResponse.json(body),
  projects: (items: ProjectItem[]) => HttpResponse.json({ items, next_cursor: null } satisfies ProjectList),
  ready: () => HttpResponse.json({ status: "ok", checks: { postgres: "ok" } } satisfies HealthReady),
};

/** Both read-only screens' data, on both origins, in one call. */
export function serveApi(opts: { settings?: SettingsOut; projects?: ProjectItem[] } = {}) {
  const settings = opts.settings ?? settingsFixture();
  const projects = opts.projects ?? [];
  server.use(
    http.get(`${API}/api/v1/settings`, () => json.settings(settings)),
    http.get(`${API}/api/v1/projects`, () => json.projects(projects)),
  );
}
