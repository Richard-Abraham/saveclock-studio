import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoSeriousViolations } from "../../../../tests/a11y";
import { json, projectFixture, serveApi, server, settingsFixture, WEB } from "../../../../tests/msw";
import { ProjectsContent } from "../project-list/projects-content";
import { SettingsContent } from "../settings-sections/settings-content";
import { UnreachableBanner } from "../health-indicator/unreachable-banner";
import { AppHeader } from "./app-header";
import { PageTitle } from "./page-title";
import { Providers } from "./providers";
import { RouteFocus } from "./route-focus";
import { SkipLink } from "./skip-link";

let pathname = "/";
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }), usePathname: () => pathname }));
vi.mock("@/lib/api/browser", async () => {
  const { createApi } = await import("@/lib/api/client");
  return { browserApi: createApi("http://localhost:3000") };
});

beforeEach(() => {
  pathname = "/";
  server.use(http.get(`${WEB}/api/v1/health/ready`, () => json.ready()));
});

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <SkipLink />
      <AppHeader />
      <main id="main" tabIndex={-1}>
        <UnreachableBanner />
        {children}
      </main>
    </Providers>
  );
}

describe("app frame", () => {
  it("tabs through skip link, brand, Projects, Settings in that order", async () => {
    render(
      <Frame>
        <PageTitle>Projects</PageTitle>
      </Frame>,
    );
    const user = userEvent.setup();
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    await user.tab();
    expect(screen.getByRole("link", { name: "SaveClock Studio" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Projects" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Settings" })).toHaveFocus();
  });

  it("has a main nav of exactly two links, marks the current one, and no New link", () => {
    pathname = "/settings";
    render(
      <Frame>
        <PageTitle>Settings</PageTitle>
      </Frame>,
    );
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav.querySelectorAll("a")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Projects" })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("link", { name: /new/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "SaveClock Studio" })).toHaveAttribute("translate", "no");
  });

  it("has banner and main landmarks and one h1", () => {
    render(
      <Frame>
        <PageTitle>Projects</PageTitle>
      </Frame>,
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("moves focus to the h1 after a route change, not on first render", () => {
    const { rerender } = render(
      <Frame>
        <PageTitle>Projects</PageTitle>
        <RouteFocus />
      </Frame>,
    );
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveFocus();
    pathname = "/settings";
    rerender(
      <Frame>
        <PageTitle>Projects</PageTitle>
        <RouteFocus />
      </Frame>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });

  it("passes axe as a whole page: S9 with a project, and S11", async () => {
    serveApi({ projects: [projectFixture()] });
    const s9 = render(
      <Frame>
        <PageTitle>Projects</PageTitle>
        {await ProjectsContent()}
      </Frame>,
    );
    await screen.findByText("Server ok");
    await expectNoSeriousViolations(s9.container);
    s9.unmount();

    serveApi({ settings: settingsFixture({ tuning: null }) });
    const s11 = render(
      <Frame>
        <PageTitle>Settings</PageTitle>
        {await SettingsContent()}
      </Frame>,
    );
    await screen.findByText("Server ok");
    await expectNoSeriousViolations(s11.container);
  });
});
