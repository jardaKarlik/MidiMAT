import type { CSSProperties, HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export type GlowTone = "accent" | "violet";

const TONES: Record<GlowTone, string> = {
  accent: "51, 204, 255",
  violet: "192, 132, 252",
};

export interface GlowingCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Render the accent halo. */
  glow?: boolean;
  tone?: GlowTone;
}

/**
 * Bordered card with an optional accent glow (box-shadow halo).
 * Hand-rolled to stay MIT-clean — no closed-source UI dependency.
 */
export function GlowingCard({
  glow = false,
  tone = "accent",
  className,
  style,
  children,
  ...rest
}: GlowingCardProps) {
  const rgb = TONES[tone];

  const glowStyle: CSSProperties | undefined = glow
    ? {
        boxShadow: `0 0 0 1px rgba(${rgb}, 0.28), 0 14px 46px -16px rgba(${rgb}, 0.62)`,
        borderColor: `rgba(${rgb}, 0.42)`,
      }
    : undefined;

  return (
    <div
      className={cn(
        "relative rounded-xl border border-border bg-bg-card transition-shadow duration-300",
        className,
      )}
      style={{ ...glowStyle, ...style }}
      {...rest}
    >
      {children}
    </div>
  );
}
