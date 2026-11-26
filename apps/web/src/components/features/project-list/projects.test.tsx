import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoSeriousViolations } from "../../../../tests/a11y";
import { API, envelope, projectFixture, serveApi, server, settingsFixture } from "../../../../tests/msw";
import { ProjectList } from "./project-list";
import { ProjectsContent } from "./projects-content";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }), usePathname: () => "/" }));

const EMPTY = "No videos yet. Choose a song to make your first one.";
const NOW = new Date(2026, 10, 26, 15, 0);

beforeEach(() => {
  refresh.mockClear();
});

describe("ProjectList", () => {
  it("shows the exact empty sentence once and no list", () => {
    render(<ProjectList items={[]} now={NOW} />);
    expect(screen.getByText(EMPTY)).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders one row per project with its pill label and edited time", () => {
    render(
      <ProjectList
        now={NOW}
        items={[
          projectFixture({
            title: "night_drive_final",
            ui_status: "draft",
            last_activity_at: new Date(2026, 10, 26, 9).toISOString(),
          }),
          projectFixture({
            id: "22222222-2222-4222-8222-222222222222",
            title: "morning_run",
            ui_status: "ready",
            last_activity_at: new Date(2026, 10, 23, 9).toISOString(),
          }),
        ]}
      />,
    );
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]!).getByText("night_drive_final")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("Draft")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("Edited today")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("Ready")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("Edited 3 days ago")).toBeInTheDocument();
    expect(screen.queryByText(EMPTY)).not.toBeInTheDocument();
  });

  it("puts the full title in a title attribute and labels an untitled project", () => {
    render(<ProjectList now={NOW} items={[projectFixture({ title: null })]} />);
    expect(screen.getByText("Untitled")).toHaveAttribute("title", "Untitled");
  });
});
describe("ProjectsContent (the S9 body, rendered from real API responses)", () => {
  it("shows the disk line from GET /settings and the empty state", async () => {
    serveApi({ settings: settingsFixture(), projects: [] });
    const { container } = render(await ProjectsContent());
    expect(screen.getByText(/3\.2 GB of 40 GB used/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage storage" })).toHaveAttribute("href", "/settings#storage");
    expect(screen.getByRole("progressbar", { name: "Disk usage" })).toHaveAttribute("aria-valuenow", "8");
    expect(screen.getByText(EMPTY)).toBeInTheDocument();
    expect(screen.queryByText(/Disk is/)).not.toBeInTheDocument();
    await expectNoSeriousViolations(container);
  });

  it("lists the project and takes every figure from the response, not from markup", async () => {
    serveApi({
      settings: settingsFixture({
        disk: { ...settingsFixture().disk, volume: { total: 500e9, free: 123e9 } },
      }),
      projects: [projectFixture({ title: "seeded song" })],
    });
    render(await ProjectsContent());
    expect(screen.getByText(/377 GB of 500 GB used/)).toBeInTheDocument();
    expect(screen.getByText("seeded song")).toBeInTheDocument();
  });

  it("warns at 90 % or more and links to Settings", async () => {
    serveApi({
      settings: settingsFixture({
        disk: { ...settingsFixture().disk, volume: { total: 100e9, free: 6.5e9 } },
      }),
    });
    render(await ProjectsContent());
    expect(
      screen.getByText(/Disk is 93% full\. Clean up intermediates or delete old projects\./),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Settings" })).toHaveAttribute(
      "href",
      expect.stringContaining("/settings"),
    );
  });

  it("shows no warning just below 90 %", async () => {
    serveApi({
      settings: settingsFixture({ disk: { ...settingsFixture().disk, volume: { total: 1000, free: 101 } } }),
    });
    render(await ProjectsContent());
    expect(screen.queryByText(/Disk is/)).not.toBeInTheDocument();
  });

  it("shows the error and a Retry that asks the server to re-render", async () => {
    server.use(
      http.get(`${API}/api/v1/projects`, () =>
        HttpResponse.json(envelope("internal_error"), { status: 500 }),
      ),
      http.get(`${API}/api/v1/settings`, () => HttpResponse.json(settingsFixture())),
    );
    const { container } = render(await ProjectsContent());
    expect(screen.getByText("We couldn’t load your projects.")).toBeInTheDocument();
    expect(screen.queryByText(EMPTY)).not.toBeInTheDocument();
    const retry = screen.getByRole("button", { name: "Retry" });
    expect(retry).toHaveAccessibleDescription("We couldn’t load your projects.");
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    await userEvent.click(retry);
    expect(refresh).toHaveBeenCalledTimes(1);
    // the refresh mock changes nothing, so the error is still here: the retry failed
    expect(await screen.findByText("Still couldn’t load. Try again.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Still couldn’t load. Try again.");
    await expectNoSeriousViolations(container);
  });

  it("treats a failing GET /settings as the same single failure", async () => {
    server.use(
      http.get(`${API}/api/v1/projects`, () => HttpResponse.json({ items: [], next_cursor: null })),
      http.get(`${API}/api/v1/settings`, () => HttpResponse.error()),
    );
    render(await ProjectsContent());
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);
    expect(screen.getByText("We couldn’t load your projects.")).toBeInTheDocument();
  });
});
