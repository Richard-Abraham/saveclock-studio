import axe from "axe-core";
import { expect } from "vitest";

/**
 * axe on a rendered container: 0 serious or critical violations (NFR-014). `color-contrast` cannot be
 * computed in jsdom (no layout); the token contrast test covers it for both colour schemes.
 */
export async function expectNoSeriousViolations(container: Element): Promise<void> {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  const serious = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.html).join(" | ")}`)).toEqual([]);
}
