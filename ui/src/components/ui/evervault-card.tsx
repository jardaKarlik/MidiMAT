import { useRef, type CSSProperties, type HTMLAttributes, type MouseEvent } from "react";

import { cn } from "../../lib/cn";

export interface EvervaultCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Radius (px) of the pointer spotlight. */
  spotlight?: number;
}

const initialVars = { "--mx": "50%", "--my": "50%" } as CSSProperties;

/**
 * Card whose soft spotlight and glowing border follow the pointer.
 * Aceternity-inspired but hand-rolled with plain React + CSS — no closed deps.
 * The pointer position is written to CSS custom properties (`--mx`/`--my`) so
 * the browser composites the gradients without React re-rendering.
 */
export function EvervaultCard({
  spotlight = 240,
  className,
  children,
  onMouseMove,
  ...rest
}: EvervaultCardProps) {
  const ref = useRef<HTMLDivElement>(null);

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>): void => {
    onMouseMove?.(event);
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${event.clientX - rect.left}px`);
    el.style.setProperty("--my", `${event.clientY - rect.top}px`);
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-border bg-bg-card",
        className,
      )}
      style={{ ...initialVars, ...rest.style }}
      {...rest}
    >
      {/* Soft interior spotlight. */}
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        aria-hidden="true"
        style={{
          background: `radial-gradient(${spotlight}px circle at var(--mx) var(--my), rgba(51, 204, 255, 0.14), transparent 62%)`,
        }}
      />
      {/* Accent/violet glow restricted to the 1px border ring via mask-composite. */}
      <div
        className="pointer-events-none absolute inset-0 rounded-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        aria-hidden="true"
        style={
          {
            padding: 1,
            background: `radial-gradient(${spotlight * 0.8}px circle at var(--mx) var(--my), rgba(192, 132, 252, 0.55), transparent 68%)`,
            WebkitMask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
            WebkitMaskComposite: "xor",
            maskComposite: "exclude",
          } as CSSProperties
        }
      />
      <div className="relative">{children}</div>
    </div>
  );
}
