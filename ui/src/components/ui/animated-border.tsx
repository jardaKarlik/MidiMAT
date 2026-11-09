import type { HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export interface AnimatedBorderProps extends HTMLAttributes<HTMLDivElement> {
  /** Rotate the gradient (accent ↔ violet) continuously. */
  active?: boolean;
  radiusClassName?: string;
}

/**
 * A 1px gradient border wrapper. The gradient is a conic sweep rendered behind
 * an inset card; `active` sets it spinning (respects prefers-reduced-motion via
 * `.mm-spin-slow`).
 */
export function AnimatedBorder({
  active = false,
  radiusClassName = "rounded-xl",
  className,
  children,
  ...rest
}: AnimatedBorderProps) {
  return (
    <div className={cn("relative p-px", radiusClassName, className)} {...rest}>
      <div className={cn("absolute inset-0 overflow-hidden", radiusClassName)} aria-hidden="true">
        <div
          className={cn("absolute -inset-[120%] opacity-70", active && "mm-spin-slow")}
          style={{
            background:
              "conic-gradient(from 0deg, var(--color-accent), var(--color-accent-2), var(--color-accent))",
          }}
        />
      </div>
      <div className={cn("relative h-full w-full bg-bg-card", radiusClassName)}>{children}</div>
    </div>
  );
}
