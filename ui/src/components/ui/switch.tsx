import { cn } from "../../lib/cn";

export interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** Accessible name for the control. */
  label: string;
  disabled?: boolean;
}

/** Minimal accessible toggle used by the Status screen switches. */
export function Switch({ checked, onChange, label, disabled = false }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60",
        checked ? "border-accent/50 bg-accent/30" : "border-border bg-bg-elevated",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <span
        className={cn(
          "absolute h-3.5 w-3.5 rounded-full transition-transform duration-200",
          checked ? "translate-x-[18px] bg-accent" : "translate-x-[3px] bg-text-dim",
        )}
      />
    </button>
  );
}
