"use client";

import { Button, Callout } from "@/components/ui";

/** Unexpected render error. Next 16 passes `retry` (re-fetch and re-render the segment). */
export default function ErrorPage({ retry }: { error: unknown; retry: () => void }) {
  return (
    <Callout
      variant="danger"
      title="This page couldn’t be shown."
      id="page-error"
      className="mt-6"
      actions={
        <Button
          aria-describedby="page-error"
          onClick={() => {
            retry();
          }}
        >
          Retry
        </Button>
      }
    >
      Reload it. If it keeps happening, check that SaveClock is running on this computer.
    </Callout>
  );
}
