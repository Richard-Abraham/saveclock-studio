import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { directApiBase } from "@/lib/api/direct";

import { server } from "../../../../tests/msw";
import { DevDriver } from "./dev-driver";

const BASE = directApiBase();
const PID = "11111111-1111-4111-8111-111111111111";
const RID = "22222222-2222-4222-8222-222222222222";

class FakeEventSource {
  static last: FakeEventSource | undefined;
  readonly listeners = new Map<string, (event: Event) => void>();
  closed = false;
  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }
  addEventListener(name: string, listener: (event: Event) => void) {
    this.listeners.set(name, listener);
  }
  close() {
    this.closed = true;
  }
  emit(name: string, data: unknown) {
    this.listeners.get(name)?.(Object.assign(new Event(name), { data: JSON.stringify(data) }));
  }
}

beforeEach(() => {
  FakeEventSource.last = undefined;
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DevDriver", () => {
  it("uploads, follows the stream on the direct origin, renders and links the downloads", async () => {
    server.use(
      http.post(`${BASE}/api/v1/projects`, () => HttpResponse.json({ id: PID }, { status: 201 })),
      http.post(`${BASE}/api/v1/projects/${PID}/song`, () =>
        HttpResponse.json({ job_id: RID, ui_status: "analysing" }, { status: 202 }),
      ),
      http.post(`${BASE}/api/v1/projects/${PID}/renders`, () =>
        HttpResponse.json({ render_id: RID }, { status: 202 }),
      ),
    );
    const user = userEvent.setup();
    render(<DevDriver />);
    await user.upload(
      screen.getByLabelText("Song"),
      new File([new Uint8Array([1, 2])], "song.mp3", { type: "audio/mpeg" }),
    );
    await user.click(screen.getByRole("button", { name: "Generate" }));

    await waitFor(() => {
      expect(FakeEventSource.last?.url).toBe(`${BASE}/api/v1/projects/${PID}/events`);
    });
    expect(screen.getByRole("button", { name: "Render" })).toBeDisabled();

    FakeEventSource.last?.emit("state", { status: "draft_ready", ui_status: "draft", flags: {} });
    FakeEventSource.last?.emit("progress", { step: "search", pct: 40, message_key: "searching" });
    await waitFor(() => {
      expect(screen.getByText("search 40% searching")).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "Render" }));

    FakeEventSource.last?.emit("render_ready", { render_id: RID });
    const link = await screen.findByRole("link", { name: "Silent video" });
    expect(link).toHaveAttribute("href", `${BASE}/api/v1/renders/${RID}/download?kind=silent_video`);
    expect(screen.queryByRole("link", { name: /Mode A/ })).not.toBeInTheDocument();
    expect(FakeEventSource.last?.closed).toBe(true); // a terminal event ends the stream
  });

  it("shows the API's error code when the upload is refused", async () => {
    server.use(
      http.post(`${BASE}/api/v1/projects`, () => HttpResponse.json({ id: PID }, { status: 201 })),
      http.post(`${BASE}/api/v1/projects/${PID}/song`, () =>
        HttpResponse.json(
          {
            error: {
              code: "file_rejected",
              message: "too short",
              details: null,
              request_id: "r",
              doc_url: null,
            },
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<DevDriver />);
    await user.upload(
      screen.getByLabelText("Song"),
      new File([new Uint8Array([1])], "s.mp3", { type: "audio/mpeg" }),
    );
    await user.click(screen.getByRole("button", { name: "Generate" }));
    expect(await screen.findByText("file_rejected: too short")).toBeInTheDocument();
    expect(FakeEventSource.last).toBeUndefined();
  });
});
