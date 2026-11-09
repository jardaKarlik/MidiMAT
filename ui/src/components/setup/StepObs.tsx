import { Check, Copy, Download } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { OVERLAY_URL } from "@/lib/constants";
import { SetupStepCard } from "./setup-step-card";
import { stepStatusText } from "./step-status";
import type { StepProps } from "./types";

/** Step 5 — detect OBS/Streamlabs and surface the Browser Source settings to use. */
export function StepObs({ deps, status, detail, connected, onRun }: StepProps) {
  const detected = deps.obs;
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const copy = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    navigator.clipboard.writeText(OVERLAY_URL).then(
      () => {
        setCopied(true);
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => setCopied(false), 1500);
      },
      () => {
        /* clipboard blocked (e.g. insecure origin) — the URL stays selectable. */
      },
    );
  }, []);

  const statusText = stepStatusText(status, detail, {
    pending: detected ? "OBS detected" : "OBS not detected",
    running: "Looking for OBS…",
    done: "OBS ready — add a Browser Source",
    error: "OBS check failed",
  });

  return (
    <SetupStepCard
      title="Add the OBS Browser Source"
      description={
        <>
          In OBS Studio or Streamlabs, add a <strong>Browser Source</strong> and paste the overlay URL below. Set the
          width and height to match your overlay layout. The source reloads automatically as MIDI events arrive.
        </>
      }
      status={status}
      statusText={statusText}
      detail={detail}
      connected={connected}
      primary={{
        label: detected ? "Re-check" : "Re-check for OBS",
        onClick: onRun,
        disabled: status === "running",
      }}
    >
      <div className="rounded-md border bg-inset p-4">
        <p className="text-xs text-muted-foreground">Browser Source URL</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <code className="min-w-0 flex-1 break-all font-mono text-sm text-primary">{OVERLAY_URL}</code>
          <Button variant="outline" size="sm" onClick={copy}>
            {copied ? <Check /> : <Copy />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>

      {!detected ? (
        <p className="mt-3 text-sm text-muted-foreground">
          OBS not found on this machine.{" "}
          <a
            href="https://obsproject.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
          >
            Download OBS <Download className="size-3.5" />
          </a>{" "}
          — install it, then click Re-check.
        </p>
      ) : null}
    </SetupStepCard>
  );
}
