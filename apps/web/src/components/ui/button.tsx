import type { ComponentProps } from "react";

import { Icon } from "./icons";

type ButtonProps = Omit<ComponentProps<"button">, "type"> & {
  /** Spinner plus `loadingLabel`; the button stays focusable so focus is never lost. */
  loading?: boolean;
  loadingLabel?: string;
};

/**
 * Secondary button, size md (44 px). `primary`, `ghost`, `danger`, `sm` and `lg` are not built:
 * nothing in the shell uses them (add on first use, DESIGN §5).
 */
export function Button({ loading = false, loadingLabel, children, className = "", ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      aria-busy={loading || undefined}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-control border border-line-strong bg-surface-2 px-4 font-medium text-ink transition-[background-color,transform] duration-150 ease-out hover:bg-line active:scale-[0.98] active:duration-90 motion-reduce:active:scale-100 ${className}`}
      {...rest}
    >
      {loading ? <Icon name="loader" className="size-4 motion-safe:animate-spin" /> : null}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}
