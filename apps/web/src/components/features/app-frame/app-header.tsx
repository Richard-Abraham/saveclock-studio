import Link from "next/link";

import { HealthIndicator } from "../health-indicator/health-indicator";
import { AppNav } from "./app-nav";

/** The logo mark: a clock face whose second hand is a tick (DESIGN §3.5). Decorative. */
function LogoMark() {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" className="size-7 shrink-0" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.75" />
      <rect x="11" y="4.5" width="2" height="9" rx="1" className="fill-tick" />
    </svg>
  );
}

export function AppHeader() {
  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 md:px-6 lg:min-h-16 lg:px-8">
      <Link
        href="/"
        translate="no"
        className="flex min-h-11 items-center gap-2 font-display text-h3 font-semibold text-ink"
      >
        <LogoMark />
        SaveClock Studio
      </Link>
      <AppNav />
      <HealthIndicator />
    </header>
  );
}
