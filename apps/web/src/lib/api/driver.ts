import type { components } from "@saveclock/contracts";

import { call, type Api } from "./client";
import { directApiBase } from "./direct";

type Schemas = components["schemas"];
export type DownloadKind = Schemas["DownloadKind"];
/** One label per kind; the Record type makes a kind added or removed in the API a compile error here. */
export const KIND_LABEL: Record<DownloadKind, string> = {
  silent_video: "Silent video",
  cutlist_json: "Cut list (JSON)",
  cutlist_csv: "Cut list (CSV)",
  with_song: "Video with song (Mode A)",
};

export type DriverInput = { vibe: string; keywords: string; duration: 15 | 30 | 60 };

/** The project options of the form: only what was filled in is sent (the API owns every rule). */
export function projectOptions(input: DriverInput): Schemas["ProjectOptions"] {
  const keywords = input.keywords
    .split(",")
    .map((word) => word.trim())
    .filter(Boolean);
  return {
    density: 0,
    style: "default",
    duration: input.duration,
    ...(input.vibe.trim() ? { vibe: input.vibe.trim() } : {}),
    ...(keywords.length > 0 ? { keywords_override: keywords } : {}),
  };
}

export function createProject(api: Api, input: DriverInput): Promise<Schemas["ProjectDetail"]> {
  return call(() => api.POST("/api/v1/projects", { body: { options: projectOptions(input) } }));
}

/**
 * The song goes as the raw request body (never multipart), with its name percent-encoded in
 * `X-Filename`. The browser adds `Content-Length` for a Blob and `Origin` on its own.
 */
export function uploadSong(
  api: Api,
  projectId: string,
  file: Blob & { name: string },
): Promise<Schemas["UploadAccepted"]> {
  return call(() =>
    api.POST("/api/v1/projects/{project_id}/song", {
      params: { path: { project_id: projectId }, header: { "x-filename": encodeURIComponent(file.name) } },
      headers: { "Content-Type": "application/octet-stream" },
      // the contract types an octet-stream body as string; the serializer passes the Blob through
      body: file as unknown as string,
      bodySerializer: (body: unknown) => body,
    }),
  );
}

export function startRender(api: Api, projectId: string): Promise<Schemas["RenderAccepted"]> {
  return call(() =>
    api.POST("/api/v1/projects/{project_id}/renders", { params: { path: { project_id: projectId } } }),
  );
}

export function requestModeA(api: Api, renderId: string): Promise<Schemas["ModeAAccepted"]> {
  return call(() =>
    api.POST("/api/v1/renders/{render_id}/mode-a", { params: { path: { render_id: renderId } } }),
  );
}

/** Plain links: the browser sends no custom header and no Origin on a navigation. */
export function downloadUrl(renderId: string, kind: DownloadKind): string {
  return `${directApiBase()}/api/v1/renders/${encodeURIComponent(renderId)}/download?kind=${kind}`;
}

export function eventsUrl(projectId: string): string {
  return `${directApiBase()}/api/v1/projects/${encodeURIComponent(projectId)}/events`;
}
