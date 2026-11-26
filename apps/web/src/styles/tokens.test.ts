// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { THEME_COLOR } from "./theme-color";

const css = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");

/** The token values of one scheme, read from tokens.css (never retyped here). */
function scheme(block: RegExp): Record<string, string> {
  const body = block.exec(css)?.[1];
  if (body === undefined) throw new Error(`block not found: ${block}`);
  return Object.fromEntries(
    [...body.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6});/g)].map((m) => [m[1]!, m[2]!]),
  );
}

const light = scheme(/:root \{([^}]*)\}/);
const dark = scheme(/prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme="light"\]\) \{([^}]*)\}/);

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

// Every foreground/background pairing the shell renders (plan 002 design spec §3), WCAG 2.2 AA.
const TEXT: [string, string][] = [
  ["ink", "bg"],
  ["ink", "surface"],
  ["ink", "surface-2"],
  ["ink-muted", "bg"],
  ["ink-muted", "surface"],
  ["ink-muted", "surface-2"],
  ["ink-subtle", "bg"],
  ["ink-subtle", "surface"],
  ["tick", "bg"],
  ["tick", "surface"],
  ["warn-ink", "warn-bg"],
];
const UI: [string, string][] = [
  ["lock", "surface-2"],
  ["danger", "surface-2"],
  ["danger", "surface"],
  ["tick", "surface-2"],
  ["ink-muted", "surface-2"],
  ["line-strong", "bg"],
  ["focus", "bg"],
  ["focus", "surface"],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s tokens", (_name, tokens) => {
  it("defines every token the shell uses", () => {
    for (const name of new Set([...TEXT, ...UI].flat())) expect(tokens[name], name).toMatch(/^#[0-9a-f]{6}$/);
  });

  it.each(TEXT)("text %s on %s is at least 4.5:1", (fg, bg) => {
    expect(contrast(tokens[fg]!, tokens[bg]!)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(UI)("component %s on %s is at least 3:1", (fg, bg) => {
    expect(contrast(tokens[fg]!, tokens[bg]!)).toBeGreaterThanOrEqual(3);
  });
});

describe("the known weak pairing", () => {
  it("ink-subtle on surface-2 fails 4.5:1 in light mode, which is why it is never used", () => {
    expect(contrast(light["ink-subtle"]!, light["surface-2"]!)).toBeLessThan(4.5);
  });
});

describe("theme-color meta values", () => {
  it("equal the --bg token of each scheme", () => {
    expect(THEME_COLOR.light).toBe(light["bg"]);
    expect(THEME_COLOR.dark).toBe(dark["bg"]);
  });
});
