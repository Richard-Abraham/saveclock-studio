import { Callout } from "@/components/ui";

import { RetryButton } from "./retry-button";

/** A failed read-only load: say what happened, offer Retry (safe: both screens only GET). */
export function LoadError({ message, id }: { message: string; id: string }) {
  return (
    <Callout variant="danger" id={id} actions={<RetryButton describedBy={id} />}>
      {message}
    </Callout>
  );
}
