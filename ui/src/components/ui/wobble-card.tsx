import type { HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export interface WobbleCardProps extends HTMLAttributes<HTMLDivElement> {
  /** When true the card "breathes" with a very subtle scale loop. */
  active?: boolean;
}

/**
 * Card with a soft breathing scale when `active` (used for the running server
 * card). The scale is intentionally tiny to avoid blurring text; the loop is
 * disabled under prefers-reduced-motion (`.mm-breathe`).
 */
export function WobbleCard({ active = false, className, children, ...rest }: WobbleCardProps) {
  return (
    <div
      className={cn(
        "relative rounded-xl border border-border bg-bg-card transition-colors duration-500",
        active && "mm-breathe border-accent/30",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
