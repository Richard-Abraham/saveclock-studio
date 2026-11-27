import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DevPage, { dynamic } from "./page";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("/dev (the throwaway driver, T-2.13)", () => {
  it("is not found while DEV_DRIVER is unset", () => {
    vi.stubEnv("DEV_DRIVER", undefined);
    expect(() => DevPage()).toThrow();
  });

  it("is not found for a flag that is not 1 or true", () => {
    vi.stubEnv("DEV_DRIVER", "0");
    expect(() => DevPage()).toThrow();
  });

  it("renders the form when DEV_DRIVER=1", () => {
    vi.stubEnv("DEV_DRIVER", "1");
    render(DevPage());
    expect(screen.getByRole("heading", { level: 1, name: "Developer driver" })).toBeInTheDocument();
    expect(screen.getByLabelText("Song")).toBeInTheDocument();
    expect(screen.getByLabelText("Vibe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
  });

  it("reads the flag per request, never at build time", () => {
    expect(dynamic).toBe("force-dynamic");
  });
});
