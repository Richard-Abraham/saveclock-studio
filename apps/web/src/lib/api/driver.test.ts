import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../../../tests/msw";
import { createApi } from "./client";
import {
  createProject,
  downloadUrl,
  eventsUrl,
  projectOptions,
  requestModeA,
  startRender,
  uploadSong,
} from "./driver";
import { directApiBase } from "./direct";

const BASE = directApiBase();
const api = createApi(BASE);
const PID = "11111111-1111-4111-8111-111111111111";
const RID = "22222222-2222-4222-8222-222222222222";

describe("projectOptions", () => {
  it("sends only what was filled in", () => {
    expect(projectOptions({ vibe: "  ", keywords: "", duration: 30 })).toEqual({
      density: 0,
      style: "default",
      duration: 30,
    });
    expect(projectOptions({ vibe: " calm ", keywords: "night drive, , city ", duration: 15 })).toEqual({
      density: 0,
      style: "default",
      duration: 15,
      vibe: "calm",
      keywords_override: ["night drive", "city"],
    });
  });
});

describe("the dev driver's API calls (direct origin, OQ-26 Branch B)", () => {
  it("creates a project at the API's own origin", async () => {
    let seen: unknown;
    server.use(
      http.post(`${BASE}/api/v1/projects`, async ({ request }) => {
        seen = await request.json();
        return HttpResponse.json({ id: PID }, { status: 201 });
      }),
    );
    expect((await createProject(api, { vibe: "calm", keywords: "", duration: 30 })).id).toBe(PID);
    expect(seen).toEqual({ options: { density: 0, style: "default", duration: 30, vibe: "calm" } });
  });

  it("uploads the song as the raw body, never multipart, with a percent-encoded X-Filename and no Origin", async () => {
    let captured:
      { type: string | null; name: string | null; origin: string | null; bytes: number[] } | undefined;
    server.use(
      http.post(`${BASE}/api/v1/projects/${PID}/song`, async ({ request }) => {
        captured = {
          type: request.headers.get("content-type"),
          name: request.headers.get("x-filename"),
          origin: request.headers.get("origin"),
          bytes: [...new Uint8Array(await request.arrayBuffer())],
        };
        return HttpResponse.json({ job_id: RID, ui_status: "analysing" }, { status: 202 });
      }),
    );
    const song = new File([new Uint8Array([1, 2, 3, 4])], "night drive é.mp3");
    expect((await uploadSong(api, PID, song)).job_id).toBe(RID);
    expect(captured?.type).toBe("application/octet-stream");
    expect(captured?.type).not.toMatch(/multipart/);
    expect(captured?.name).toBe(encodeURIComponent("night drive é.mp3"));
    expect(captured?.origin).toBeNull();
    expect(captured?.bytes).toEqual([1, 2, 3, 4]);
  });

  it("starts a render and requests Mode A", async () => {
    server.use(
      http.post(`${BASE}/api/v1/projects/${PID}/renders`, () =>
        HttpResponse.json({ render_id: RID }, { status: 202 }),
      ),
      http.post(`${BASE}/api/v1/renders/${RID}/mode-a`, () =>
        HttpResponse.json({ render_id: RID, mode_a_state: "queued" }, { status: 202 }),
      ),
    );
    expect((await startRender(api, PID)).render_id).toBe(RID);
    expect((await requestModeA(api, RID)).mode_a_state).toBe("queued");
  });

  it("builds plain download and event URLs on the direct origin", () => {
    expect(downloadUrl(RID, "with_song")).toBe(`${BASE}/api/v1/renders/${RID}/download?kind=with_song`);
    expect(eventsUrl(PID)).toBe(`${BASE}/api/v1/projects/${PID}/events`);
  });
});
