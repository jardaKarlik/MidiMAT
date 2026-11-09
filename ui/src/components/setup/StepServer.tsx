import { SetupStepCard } from "./setup-step-card";
import { stepStatusText } from "./step-status";
import type { StepProps } from "./types";
import { HTTP_BASE, WS_URL } from "@/lib/constants";

/** Step 4 — start the bundled sidecar and show it running. */
export function StepServer({ deps, status, detail, connected, onRun }: StepProps) {
  const running = deps.server;

  const statusText = stepStatusText(status, detail, {
    pending: running ? "Server already running" : "Server stopped",
    running: "Starting server…",
    done: "Server running",
    error: "Server failed to start",
  });

  return (
    <SetupStepCard
      title="Start the server"
      description={
        <>
          MidiMAT launches the bundled Python sidecar. It serves the overlay that OBS reads and a WebSocket that
          carries live MIDI events. It starts on demand and stops with the app.
        </>
      }
      status={status}
      statusText={statusText}
      detail={detail}
      connected={connected}
      primary={{
        label: running ? "Restart server" : "Start server",
        onClick: onRun,
        disabled: status === "running",
      }}
    >
      <div className="rounded-md border bg-inset p-4 font-mono text-sm">
        <p className="text-muted-foreground">Overlay (HTTP)</p>
        <p className="mt-1 text-primary">{HTTP_BASE}</p>
        <p className="mt-3 text-muted-foreground">Live events (WebSocket)</p>
        <p className="mt-1 text-primary">{WS_URL}</p>
      </div>
    </SetupStepCard>
  );
}
