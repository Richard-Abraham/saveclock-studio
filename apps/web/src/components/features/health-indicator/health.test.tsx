import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoSeriousViolations } from "../../../../tests/a11y";
import { envelope, json, server, WEB } from "../../../../tests/msw";
import { HealthIndicator } from "./health-indicator";
import { UnreachableBanner } from "./unreachable-banner";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }), usePathname: () => "/" }));
// Same client, but with an absolute base URL: relative fetches do not exist outside a browser.
vi.mock("@/lib/api/browser", async () => {
  const { createApi: make } = await import("@/lib/api/client");
  return { browserApi: make("http://localhost:3000") };
});

const READY = `${WEB}/api/v1/health/ready`;

function frame(children: ReactNode) {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}

beforeEach(() => {
  refresh.mockClear();
});

describe("HealthIndicator", () => {
  it("is a polite live region from the first render and starts as checking", () => {
    server.use(http.get(READY, () => json.ready()));
    const { container } = frame(<HealthIndicator />);
    const region = container.querySelector("[aria-live]");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-atomic", "true");
    expect(region).toHaveTextContent("Checking server…");
  });

  it("says ok on 200", async () => {
    server.use(http.get(READY, () => json.ready()));
    const { container } = frame(<HealthIndicator />);
    expect(await screen.findByText("Server ok")).toBeInTheDocument();
    await expectNoSeriousViolations(container);
  });

  it("names the failing check on a 503 envelope", async () => {
    server.use(
      http.get(READY, () =>
        HttpResponse.json(envelope("upstream_unavailable", { checks: { postgres: "ok", redis: "error" } }), {
          status: 503,
        }),
      ),
    );
    frame(<HealthIndicator />);
    const text = await screen.findByText(/Server degraded/);
    expect(text).toHaveTextContent("Server degraded: redis");
    expect(screen.getByText("redis")).toHaveAttribute("translate", "no");
  });

  it("says unreachable on a network error", async () => {
    server.use(http.get(READY, () => HttpResponse.error()));
    frame(<HealthIndicator />);
    expect(await screen.findByText("Server unreachable")).toBeInTheDocument();
  });
});

describe("UnreachableBanner", () => {
  it("renders nothing while the server is reachable", async () => {
    server.use(http.get(READY, () => json.ready()));
    const { container } = frame(
      <>
        <HealthIndicator />
        <UnreachableBanner />
      </>,
    );
    await screen.findByText("Server ok");
    expect(container).not.toHaveTextContent("Can’t reach SaveClock.");
  });

  it("shows the exact copy with no live role when the server cannot be reached", async () => {
    server.use(http.get(READY, () => HttpResponse.error()));
    const { container } = frame(<UnreachableBanner />);
    expect(await screen.findByText("Can’t reach SaveClock.")).toBeInTheDocument();
    expect(screen.getByText("Check that it’s running on this computer.")).toBeInTheDocument();
    expect(container.querySelector("[role='alert'], [role='status'], [aria-live]")).toBeNull();
    await expectNoSeriousViolations(container);
  });

  it("retries: refetches health, refreshes the route and hands focus to the h1 once it is back", async () => {
    let up = false;
    server.use(http.get(READY, () => (up ? json.ready() : HttpResponse.error())));
    frame(
      <>
        <main>
          <h1 tabIndex={-1}>Projects</h1>
          <UnreachableBanner />
        </main>
      </>,
    );
    const retry = await screen.findByRole("button", { name: "Retry" });
    expect(retry).toHaveAccessibleDescription("Check that it’s running on this computer.");
    up = true;
    await userEvent.click(retry);
    await waitFor(() => {
      expect(screen.queryByText("Can’t reach SaveClock.")).not.toBeInTheDocument();
    });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });
});
