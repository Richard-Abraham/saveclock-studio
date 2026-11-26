import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoSeriousViolations } from "../../../../tests/a11y";
import { API, envelope, serveApi, server, settingsFixture } from "../../../../tests/msw";
import { SettingsContent } from "./settings-content";
import { SettingsSections } from "./settings-sections";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }), usePathname: () => "/settings" }));

beforeEach(() => {
  refresh.mockClear();
});

/** The dd that belongs to a dt (label). */
function valueOf(label: string): HTMLElement {
  const dt = screen.getByText(label, { selector: "dt" });
  const dd = dt.nextElementSibling;
  if (!(dd instanceof HTMLElement) || dd.tagName !== "DD") throw new Error(`no dd after ${label}`);
  return dd;
}

describe("SettingsSections", () => {
  it("is read-only: no input, select, textarea, button or switch anywhere", () => {
    const { container } = render(<SettingsSections settings={settingsFixture()} />);
    for (const role of [
      "textbox",
      "combobox",
      "listbox",
      "button",
      "switch",
      "checkbox",
      "radio",
      "slider",
      "spinbutton",
    ]) {
      expect(screen.queryAllByRole(role)).toEqual([]);
    }
    expect(container.querySelectorAll("input, select, textarea, button")).toHaveLength(0);
  });

  it("shows key status only, per key", () => {
    render(
      <SettingsSections
        settings={settingsFixture({
          keys: {
            pexels: { configured: true },
            pixabay: { configured: false },
            anthropic: { configured: true, llm_enabled: true, fallback_active: false },
          },
        })}
      />,
    );
    expect(within(valueOf("Pexels")).getByText("Set")).toBeInTheDocument();
    expect(within(valueOf("Pixabay")).getByText("Not set")).toBeInTheDocument();
    expect(within(valueOf("Claude")).getByText("Set")).toBeInTheDocument();
    expect(screen.getByText("Keys live in the server environment.")).toBeInTheDocument();
  });

  it("explains a missing Pexels key with the variable name and nothing else is nagging", () => {
    render(
      <SettingsSections
        settings={settingsFixture({
          keys: {
            pexels: { configured: false },
            pixabay: { configured: false },
            anthropic: { configured: false, llm_enabled: false, fallback_active: true },
          },
        })}
      />,
    );
    expect(within(valueOf("Pexels")).getByText("Not set")).toBeInTheDocument();
    expect(screen.getByText(/Pexels isn’t set up, so no clips can be fetched\./)).toBeInTheDocument();
    expect(screen.getByText("PEXELS_API_KEY")).toHaveAttribute("translate", "no");
    expect(screen.getByText("Optional — Claude Code can set keywords instead")).toBeInTheDocument();
    // optional keys that are off get no fix line
    expect(screen.queryByText(/PIXABAY_API_KEY/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ANTHROPIC_API_KEY/)).not.toBeInTheDocument();
  });

  it("asks for the Pixabay key only when Pixabay is switched on without one", () => {
    render(<SettingsSections settings={settingsFixture({ stock: { pixabay_enabled: true } })} />);
    expect(screen.getByText("PIXABAY_API_KEY")).toBeInTheDocument();
    expect(valueOf("Also use Pixabay")).toHaveTextContent("On");
    expect(valueOf("Pexels (primary)")).toHaveTextContent("Always on");
  });

  it("shows Pixabay off as plain text", () => {
    render(<SettingsSections settings={settingsFixture()} />);
    expect(valueOf("Also use Pixabay")).toHaveTextContent("Off");
  });

  it("lists the tuning values exactly as given", () => {
    render(<SettingsSections settings={settingsFixture()} />);
    expect(valueOf("Heavy-job concurrency")).toHaveTextContent("2");
    expect(valueOf("FFmpeg threads")).toHaveTextContent("6");
    expect(valueOf("Torch threads")).toHaveTextContent("6");
    expect(valueOf("Fetch concurrency")).toHaveTextContent("4");
    expect(valueOf("Device")).toHaveTextContent("cpu");
    expect(screen.getByText("Detected when the worker started. Change them in .env.")).toBeInTheDocument();
  });

  it("says the worker is not running when tuning is null", () => {
    render(<SettingsSections settings={settingsFixture({ tuning: null })} />);
    expect(screen.getByText("Not available: the worker isn’t running")).toBeInTheDocument();
    expect(screen.queryByText("Heavy-job concurrency")).not.toBeInTheDocument();
    expect(screen.queryByText(/Detected when the worker started/)).not.toBeInTheDocument();
  });

  it("states the cleanup window from the server value, singular and plural", () => {
    const { rerender } = render(
      <SettingsSections settings={settingsFixture({ intermediate_ttl_days: 3 })} />,
    );
    expect(
      screen.getByText(
        "Intermediates (raw clips, proxies) are cleaned up 3 days after last use. Songs and videos stay until you delete the project.",
      ),
    ).toBeInTheDocument();
    rerender(<SettingsSections settings={settingsFixture({ intermediate_ttl_days: 1 })} />);
    expect(screen.getByText(/cleaned up 1 day after last use/)).toBeInTheDocument();
  });

  it("never renders a field it was not told to show", () => {
    const canary = "CANARY-sk-live-12345";
    const settings = { ...settingsFixture(), unrelated: canary } as unknown as ReturnType<
      typeof settingsFixture
    >;
    settings.tuning = { ...settingsFixture().tuning!, source: { heavy: "auto" }, device: "cpu" };
    (settings.keys.pexels as unknown as Record<string, string>)["value"] = canary;
    const { container } = render(<SettingsSections settings={settings} />);
    expect(container).not.toHaveTextContent(canary);
    expect(container.innerHTML).not.toContain(canary);
  });

  it("has h1-to-h2 heading order and four titled sections", async () => {
    const { container } = render(<SettingsSections settings={settingsFixture()} />);
    const names = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(names).toEqual(["API keys", "Stock sources", "Storage", "Performance"]);
    expect(container.querySelector("#storage")).toHaveAccessibleName("Storage");
    await expectNoSeriousViolations(container);
  });
});

describe("SettingsContent (the S11 body, rendered from real API responses)", () => {
  it("shows the disk meter from the response and the warning at 90 %", async () => {
    serveApi({
      settings: settingsFixture({
        disk: { ...settingsFixture().disk, volume: { total: 100e9, free: 6.5e9 } },
      }),
    });
    render(await SettingsContent());
    expect(screen.getByRole("progressbar", { name: "Disk usage" })).toHaveAttribute("aria-valuenow", "93");
    expect(screen.getByText(/Disk is 93% full\./)).toBeInTheDocument();
  });

  it("shows the error with Retry when the settings cannot be loaded", async () => {
    server.use(
      http.get(`${API}/api/v1/settings`, () =>
        HttpResponse.json(envelope("internal_error"), { status: 500 }),
      ),
    );
    render(await SettingsContent());
    expect(screen.getByText("We couldn’t load your settings.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
