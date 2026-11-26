import type { ComponentProps, ElementType } from "react";

type CardProps = ComponentProps<"div"> & { as?: ElementType };

/** Flat card: surface step plus a 1 px line, no shadow (DESIGN §3.3). */
export function Card({ as: Tag = "div", className = "", ...rest }: CardProps) {
  return <Tag className={`rounded-card border border-line bg-surface ${className}`} {...rest} />;
}
