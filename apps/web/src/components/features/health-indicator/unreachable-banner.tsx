"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Callout } from "@/components/ui";
import type { HealthState } from "@/lib/api/endpoints";
import { focusMainHeading } from "@/lib/focus";

import { HEALTH_KEY, useHealth } from "./use-health";

/** Shown above the h1 on every page while the API cannot be reached (UX-SPEC §3.6). */
export function UnreachableBanner() {
  const { data } = useHealth();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [retrying, setRetrying] = useState(false);

  if (data?.kind !== "unreachable") return null;

  const retry = async () => {
    setRetrying(true);
    await queryClient.refetchQueries({ queryKey: HEALTH_KEY });
    router.refresh();
    setRetrying(false);
    // The banner is about to go away with the button that has focus: hand focus to the h1.
    if (queryClient.getQueryData<HealthState>(HEALTH_KEY)?.kind !== "unreachable") focusMainHeading();
  };

  return (
    <Callout
      variant="danger"
      title="Can’t reach SaveClock."
      id="unreachable-message"
      className="mb-6"
      actions={
        <Button
          loading={retrying}
          loadingLabel="Retrying…"
          aria-describedby="unreachable-message"
          onClick={() => void retry()}
        >
          Retry
        </Button>
      }
    >
      Check that it’s running on this computer.
    </Callout>
  );
}
