import { SetupStepCard } from "./setup-step-card";
import { stepStatusText } from "./step-status";
import type { StepProps } from "./types";

/** Step 1 — detect loopMIDI, install it if missing, and ensure the `MidiMAT` port. */
export function StepLoopMidi({ deps, status, detail, connected, onRun }: StepProps) {
  const detected = deps.loopMidi;
  const port = deps.detail?.port ?? "MidiMAT";

  const statusText = stepStatusText(status, detail, {
    pending: detected ? `loopMIDI detected · port "${port}"` : "loopMIDI not detected",
    running: "Installing loopMIDI…",
    done: `loopMIDI installed · port "${port}" created`,
    error: "Installation failed",
  });

  return (
    <SetupStepCard
      title="Install loopMIDI"
      description={
        <>
          MidiMAT needs the free <strong>loopMIDI</strong> virtual MIDI driver and a virtual port named{" "}
          <code className="rounded bg-inset px-1 py-0.5 font-mono text-[0.85em] text-foreground">{port}</code>. The
          installer is ~7.9&nbsp;MB and downloads from tobias-erichsen.de at setup time — it is not bundled inside
          MidiMAT. Windows will show a UAC prompt.
        </>
      }
      status={status}
      statusText={statusText}
      detail={detail}
      connected={connected}
      primary={{
        label: detected ? "Re-check port" : "Install & create port",
        onClick: onRun,
        disabled: status === "running",
      }}
    />
  );
}
