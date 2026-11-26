"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { focusMainHeading } from "@/lib/focus";

/** After an in-app route change focus moves to the new page's h1 (DESIGN §6). Renders nothing. */
export function RouteFocus() {
  const pathname = usePathname();
  const previous = useRef(pathname);
  useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    focusMainHeading();
  }, [pathname]);
  return null;
}
