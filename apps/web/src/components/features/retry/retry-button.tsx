"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui";
import { focusMainHeading } from "@/lib/focus";

/**
 * Re-runs the server render of the current route. Focus stays here while it runs. A successful retry
 * removes the error state (and this button with it), and focus goes to the h1. If the button is still
 * here when the refresh finishes, it failed: a polite status says so (the health indicator is the only
 * other live region, and it announces the server's state, not this).
 */
export function RetryButton({ describedBy }: { describedBy: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [failed, setFailed] = useState(false);
  const clicked = useRef(false);
  const wasPending = useRef(false);

  useEffect(() => {
    if (wasPending.current && !pending) setFailed(true);
    wasPending.current = pending;
  }, [pending]);

  useEffect(
    () => () => {
      if (clicked.current) focusMainHeading();
    },
    [],
  );

  return (
    <>
      <Button
        loading={pending}
        loadingLabel="Retrying…"
        aria-describedby={describedBy}
        onClick={() => {
          clicked.current = true;
          setFailed(false);
          startTransition(() => {
            router.refresh();
          });
        }}
      >
        Retry
      </Button>
      <span role="status" className="sr-only">
        {failed ? "Still couldn’t load. Try again." : ""}
      </span>
    </>
  );
}
