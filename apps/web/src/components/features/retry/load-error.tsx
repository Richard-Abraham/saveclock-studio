import { Callout } from "@/components/ui";
import type { ApiError } from "@/lib/api/errors";

import { RetryButton } from "./retry-button";

/** A failed read-only load: say what happened, offer Retry (safe: both screens only GET). */
export function LoadError({ message, id, error }: { message: string; id: string; error: ApiError }) {
  return (
    <Callout
      variant="danger"
      id={id}
      actions={error.advice.retry ? <RetryButton describedBy={id} /> : undefined}
    >
      {message}
    </Callout>
  );
}
