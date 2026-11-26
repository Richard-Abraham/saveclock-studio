import { describe, expect, it } from "vitest";

import { diskFigures, formatEdited, formatGB } from "./format";

const NBSP = " ";

describe("disk figures", () => {
  it.each([
    { total: 40e9, free: 36.8e9, line: `3.2${NBSP}GB of 40${NBSP}GB used`, percent: 8 },
    // rounding case: 0.04 GB prints "0 GB", a trailing ".0" is dropped
    { total: 40e9, free: 39.96e9, line: `0${NBSP}GB of 40${NBSP}GB used`, percent: 0 },
    { total: 40e9, free: 0, line: `40${NBSP}GB of 40${NBSP}GB used`, percent: 100 },
    // floored: 89.9 % must never read as 90 %
    { total: 1000, free: 101, line: `0${NBSP}GB of 0${NBSP}GB used`, percent: 89 },
    { total: 0, free: 0, line: `0${NBSP}GB of 0${NBSP}GB used`, percent: 0 },
  ])("total $total free $free", ({ total, free, line, percent }) => {
    const figures = diskFigures({ total, free });
    expect(figures.line).toBe(line);
    expect(figures.usedPercent).toBe(percent);
  });

  it("formats decimal gigabytes with one decimal at most", () => {
    expect(formatGB(1.25e9)).toBe(`1.3${NBSP}GB`);
    expect(formatGB(2e9)).toBe(`2${NBSP}GB`);
  });
});

describe("edited date", () => {
  const now = new Date(2026, 10, 26, 15, 0); // 26 Nov 2026, local time

  it.each([
    { iso: new Date(2026, 10, 26, 1, 0).toISOString(), text: "today" },
    { iso: new Date(2026, 10, 25, 23, 0).toISOString(), text: "yesterday" },
    { iso: new Date(2026, 10, 23, 12, 0).toISOString(), text: "3 days ago" },
    { iso: new Date(2026, 9, 27, 12, 0).toISOString(), text: "30 days ago" },
    { iso: new Date(2026, 9, 26, 12, 0).toISOString(), text: "26 Oct 2026" },
    { iso: new Date(2026, 10, 12, 12, 0).toISOString(), text: "14 days ago" },
  ])("$iso reads $text", ({ iso, text }) => {
    expect(formatEdited(iso, now)).toBe(text);
  });
});
