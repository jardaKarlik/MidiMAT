import type { ReactNode } from "react";

import { StatusDot, type StatusTone } from "@/components/midimat/status-dot";
import { Button } from "@/components/ui/button";
import type { SetupStepStatus } from "@/lib/ipc";

const TONE: Record<SetupStepStatus, StatusTone> = {
  pending: "warning",
  running: "warning",
  done: "success",
  error: "error",
};

export interface SetupStepCardProps {
  title: string;
  description: ReactNode;
  status: SetupStepStatus;
  /** Primary status line shown next to the dot. */
  statusText: string;
  /** Secondary muted note (e.g. the `setup:progress` detail). */
  detail?: string | undefined;
  connected: boolean;
  primary: { label: string; onClick: () => void; disabled?: boolean | undefined };
  /** Extra step-specific content (warnings, URL boxes, toggles…). */
  children?: ReactNode;
}

/**
 * Shared shell for a wizard step body: title, plain-language explanation, live
 * status row, the "no host" notice, and the step's primary action button. Keeps
 * all six steps visually identical and on the app's design tokens.
 */
export function SetupStepCard({
  title,
  description,
  status,
  statusText,
  detail,
  connected,
  primary,
  children,
}: SetupStepCardProps) {
  return (
    <section className="rounded-lg border bg-card p-7 shadow-card">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground">{description}</div>

      {children ? <div className="mt-5">{children}</div> : null}

      <p className="mt-6 flex flex-wrap items-center gap-2.5 text-sm">
        <StatusDot tone={TONE[status]} pulsing={status === "running"} />
        <span>{statusText}</span>
        {detail && detail !== statusText ? (
          <>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{detail}</span>
          </>
        ) : null}
      </p>

      {!connected ? (
        <p className="mt-3 rounded-md border bg-inset px-3 py-2 text-xs text-muted-foreground">
          Not connected to the MidiMAT host — actions are simulated for preview.
        </p>
      ) : null}

      <div className="mt-6">
        <Button size="lg" onClick={primary.onClick} disabled={primary.disabled ?? false}>
          {primary.label}
        </Button>
      </div>
    </section>
  );
}
