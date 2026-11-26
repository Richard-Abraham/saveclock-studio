"use client";

import { PageTitle } from "@/components/features/app-frame/page-title";
import { Button, Callout } from "@/components/ui";

/** Unexpected render error. Next 16 passes `retry` (re-fetch and re-render the segment). */
export default function ErrorPage({ retry }: { error: unknown; retry: () => void }) {
  return (
    <>
      <PageTitle>This page couldn’t be shown.</PageTitle>
      <Callout
        variant="danger"
        id="page-error"
        className="mt-4"
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
        Reload it. If it keeps happening, check that <span translate="no">SaveClock</span> is running on this
        computer.
      </Callout>
    </>
  );
}
