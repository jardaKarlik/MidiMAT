import type { SetupStepStatus } from "@/lib/ipc";

interface StepStatusTexts {
  pending: string;
  running: string;
  done: string;
  error: string;
}

/**
 * Resolves the single line shown beside the status dot: a `setup:progress`
 * detail when present, otherwise a sensible default for the step's state.
 */
export function stepStatusText(
  status: SetupStepStatus,
  detail: string | undefined,
  texts: StepStatusTexts,
): string {
  switch (status) {
    case "running":
      return detail ?? texts.running;
    case "done":
      return detail ?? texts.done;
    case "error":
      return detail ?? texts.error;
    default:
      return texts.pending;
  }
}
