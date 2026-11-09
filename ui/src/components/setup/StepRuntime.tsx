import { SetupStepCard } from "./setup-step-card";
import { stepStatusText } from "./step-status";
import type { StepProps } from "./types";

/**
 * Step 3 — informational only. The Python runtime is embedded in the bundled
 * sidecar, so there is nothing for the user to install.
 */
export function StepRuntime({ deps, status, detail, connected, onRun }: StepProps) {
  const statusText = stepStatusText(status, detail, {
    pending: deps.python ? "Embedded runtime detected" : "Runtime bundled with MidiMAT",
    running: "Checking runtime…",
    done: "Runtime ready — no installation required",
    error: "Runtime check failed",
  });

  return (
    <SetupStepCard
      title="Python runtime"
      description={
        <>
          The Python runtime is <strong>embedded</strong> in the bundled sidecar (~60&nbsp;MB). There is nothing to
          install and no separate Python setup — it ships inside the MidiMAT executable.
        </>
      }
      status={status}
      statusText={statusText}
      detail={detail}
      connected={connected}
      primary={{ label: "Confirm & continue", onClick: onRun, disabled: status === "running" }}
    >
      <dl className="grid gap-px overflow-hidden rounded-md border bg-border text-sm sm:grid-cols-2">
        {[
          ["MidiMAT.exe", "~35 MB"],
          ["Python sidecar", "~60 MB"],
          ["YOLO model", "~5 MB"],
          ["Overlay assets", "~1 MB"],
        ].map(([label, size]) => (
          <div key={label} className="flex items-center justify-between bg-card px-4 py-3">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-mono text-xs">{size}</dd>
          </div>
        ))}
      </dl>
    </SetupStepCard>
  );
}
