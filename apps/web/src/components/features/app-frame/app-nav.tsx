"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "Projects" },
  { href: "/settings", label: "Settings" },
] as const;

/**
 * One <nav>, restyled by breakpoint: a top-bar list from lg, a fixed bottom bar below it. Same DOM
 * position either way, so keyboard order never changes. The current page is marked by weight and a
 * 3 px ink rule (not colour alone).
 */
export function AppNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className="max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:z-40 max-lg:border-t max-lg:border-line max-lg:bg-surface max-lg:pb-[env(safe-area-inset-bottom)] lg:mr-auto"
    >
      <ul className="flex lg:gap-2">
        {ITEMS.map(({ href, label }) => {
          const current = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <li key={href} className="max-lg:flex-1">
              <Link
                href={href}
                aria-current={current ? "page" : undefined}
                className={`flex min-h-11 items-center justify-center px-3 text-body max-lg:min-h-[3.25rem] max-lg:text-small max-lg:border-t-[3px] lg:border-b-[3px] ${
                  current
                    ? "border-ink font-semibold text-ink"
                    : "border-transparent font-medium text-ink-muted hover:text-ink"
                } transition-colors duration-150 ease-out`}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
