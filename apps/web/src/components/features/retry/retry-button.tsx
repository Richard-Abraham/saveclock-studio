"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useTransition } from "react";

import { Button } from "@/components/ui";
import { focusMainHeading } from "@/lib/focus";

/**
 * Re-runs the server render of the current route. Focus stays here while it runs; when a successful
 * retry removes the error state (and this button with it), focus goes to the h1.
 */
export function RetryButton({ describedBy }: { describedBy: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const clicked = useRef(false);

  useEffect(
    () => () => {
      if (clicked.current) focusMainHeading();
    },
    [],
  );

  return (
    <Button
      loading={pending}
      loadingLabel="Retrying…"
      aria-describedby={describedBy}
      onClick={() => {
        clicked.current = true;
        startTransition(() => {
          router.refresh();
        });
      }}
    >
      Retry
    </Button>
  );
}
