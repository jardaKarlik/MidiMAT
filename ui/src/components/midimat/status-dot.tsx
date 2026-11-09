import { cn } from "@/lib/utils";

export type StatusTone = "success" | "warning" | "error";

interface StatusDotProps {
  tone: StatusTone;
  pulsing?: boolean | undefined;
  size?: "sm" | "lg" | undefined;
}

const toneClass: Record<StatusTone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-destructive",
};

export function StatusDot({ tone, pulsing = false, size = "sm" }: StatusDotProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block shrink-0 rounded-full",
        size === "sm" ? "size-2.5" : "size-4",
        toneClass[tone],
        pulsing && "pulse-dot",
      )}
    />
  );
}
