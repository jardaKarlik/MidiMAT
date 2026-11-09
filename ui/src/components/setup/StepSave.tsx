import { useCallback, useState } from "react";

import { SwitchRow } from "@/components/midimat/switch-row";
import { HostMessage, postToHost } from "@/lib/ipc";
import { SetupStepCard } from "./setup-step-card";
import { stepStatusText } from "./step-status";
import type { StepProps } from "./types";

/** Step 6 — persist state so the next launch skips dependency checks. */
export function StepSave({ status, detail, connected, onRun }: StepProps) {
  // Design default: "Always check on startup" is OFF, i.e. skip_checks = true.
  const [alwaysCheck, setAlwaysCheck] = useState(false);

  const onCheckedChange = useCallback((checked: boolean) => {
    setAlwaysCheck(checked);
    // Persist the preference immediately; the step's own completion is reported
    // separately via setup:start / setup:complete.
    postToHost(HostMessage.ConfigSave, { skipChecks: !checked });
  }, []);

  const statusText = stepStatusText(status, detail, {
    pending: "Ready to save",
    running: "Saving configuration…",
    done: "All set! Next launch will skip checks",
    error: "Could not save configuration",
  });

  return (
    <SetupStepCard
      title="Save your setup"
      description={
        <>
          MidiMAT writes its detected paths and ports to the configuration file. On the next launch it will skip the
          dependency checks and go straight to the summary.
        </>
      }
      status={status}
      statusText={statusText}
      detail={detail}
      connected={connected}
      primary={{ label: "Save & finish", onClick: onRun, disabled: status === "running" }}
    >
      <div className="divide-y rounded-lg border bg-card">
        <SwitchRow
          label="Always check on startup"
          description="Run the dependency checks every time MidiMAT opens, even after a successful setup."
          checked={alwaysCheck}
          onCheckedChange={onCheckedChange}
        />
      </div>
    </SetupStepCard>
  );
}
