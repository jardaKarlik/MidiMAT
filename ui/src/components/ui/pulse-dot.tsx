import { cn } from "../../lib/cn";

export type PulseStatus = "running" | "warn" | "error" | "idle";

const DOTS: Record<PulseStatus, string> = {
  running: "bg-success",
  warn: "bg-warn",
  error: "bg-error",
  idle: "bg-text-dim",
};

export interface PulseDotProps {
  status?: PulseStatus;
  /** Diameter in px. */
  size?: number;
  /** Accessible label; when omitted the dot is decorative. */
  label?: string;
  className?: string;
}

/**
 * Status dot with an expanding ring: green=running, amber=warn, red=error,
 * grey=idle. The ring animation is disabled under prefers-reduced-motion
 * (see `.mm-pulse-ring` in globals.css).
 */
export function PulseDot({ status = "idle", size = 10, label, className }: PulseDotProps) {
  const animates = status === "running" || status === "warn" || status === "error";
  const color = DOTS[status];

  return (
    <span
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {animates && (
        <span className={cn("absolute inset-0 rounded-full opacity-60 mm-pulse-ring", color)} />
      )}
      <span className={cn("relative rounded-full", color)} style={{ width: size, height: size }} />
    </span>
  );
}
