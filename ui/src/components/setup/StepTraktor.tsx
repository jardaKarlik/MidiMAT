import { SetupStepCard } from "./setup-step-card";
import { stepStatusText } from "./step-status";
import type { StepProps } from "./types";

/** Step 2 — locate `Traktor Settings.tsi` and inject the MidiMAT out-mappings. */
export function StepTraktor({ deps, status, detail, connected, onRun }: StepProps) {
  const detected = deps.traktor;

  const statusText = stepStatusText(status, detail, {
    pending: detected ? "Traktor settings found" : "Traktor settings not found",
    running: "Injecting MidiMAT out-mappings…",
    done: 'Configured · Generic MIDI out-port set to "MidiMAT"',
    error: "Configuration failed",
  });

  return (
    <SetupStepCard
      title="Configure Traktor"
      description={
        <>
          MidiMAT locates <code className="rounded bg-inset px-1 py-0.5 font-mono text-[0.85em] text-foreground">Traktor
          Settings.tsi</code> and surgically injects its out-mappings into the existing{" "}
          <strong>Generic MIDI</strong> device, then points that device&apos;s out-port at the{" "}
          <code className="rounded bg-inset px-1 py-0.5 font-mono text-[0.85em] text-foreground">MidiMAT</code> port.
          Your existing mappings are preserved and a timestamped backup is written first.
        </>
      }
      status={status}
      statusText={statusText}
      detail={detail}
      connected={connected}
      primary={{
        label: detected ? "Re-configure Traktor" : "Configure Traktor",
        onClick: onRun,
        disabled: status === "running",
      }}
    >
      <p className="rounded-md border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
        Close Traktor before continuing — it rewrites <span className="font-mono">Traktor Settings.tsi</span> on exit
        and would overwrite the injected mappings.
      </p>
    </SetupStepCard>
  );
}
