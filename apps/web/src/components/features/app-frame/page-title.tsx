import type { ReactNode } from "react";

/** The page's one h1. tabIndex -1 so route changes and Retry can move focus here. */
export function PageTitle({ children }: { children: ReactNode }) {
  return (
    <h1 tabIndex={-1} className="font-display text-h1 font-semibold">
      {children}
    </h1>
  );
}
