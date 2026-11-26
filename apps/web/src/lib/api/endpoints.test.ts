import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { envelope, json, projectFixture, server, settingsFixture, WEB } from "../../../tests/msw";
import { createApi } from "./client";
import { fetchHealth, getProjects, getSettings } from "./endpoints";

const api = createApi(WEB);
const READY = `${WEB}/api/v1/health/ready`;

describe("fetchHealth", () => {
  it("is ok on 200", async () => {
    server.use(http.get(READY, () => json.ready()));
    expect(await fetchHealth(api)).toEqual({ kind: "ok" });
  });

  it("is degraded on a 503 envelope and names the failing checks", async () => {
    server.use(
      http.get(READY, () =>
        HttpResponse.json(
          envelope("upstream_unavailable", {
            checks: { postgres: "ok", redis: "error", blob_volume: "error" },
          }),
          { status: 503 },
        ),
      ),
    );
    expect(await fetchHealth(api)).toEqual({ kind: "degraded", failing: ["redis", "blob_volume"] });
  });

  it("is degraded with no names when the 503 envelope lists no failing check", async () => {
    server.use(http.get(READY, () => HttpResponse.json(envelope("upstream_unavailable"), { status: 503 })));
    expect(await fetchHealth(api)).toEqual({ kind: "degraded", failing: [] });
  });

  it("is unreachable for a 503 that is not the API envelope (a proxy page)", async () => {
    server.use(http.get(READY, () => new HttpResponse("down", { status: 503 })));
    expect(await fetchHealth(api)).toEqual({ kind: "unreachable" });
  });

  it("is unreachable on a network error", async () => {
    server.use(http.get(READY, () => HttpResponse.error()));
    expect(await fetchHealth(api)).toEqual({ kind: "unreachable" });
  });
});

describe("reads", () => {
  it("returns the settings body as the API sent it", async () => {
    const body = settingsFixture({ intermediate_ttl_days: 3 });
    server.use(http.get(`${WEB}/api/v1/settings`, () => json.settings(body)));
    expect(await getSettings(api)).toEqual(body);
  });

  it("returns the first page of projects", async () => {
    const item = projectFixture();
    server.use(http.get(`${WEB}/api/v1/projects`, () => json.projects([item])));
    expect((await getProjects(api)).items).toEqual([item]);
  });
});
