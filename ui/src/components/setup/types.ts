import type { DepsStatus, SetupStepStatus } from "@/lib/ipc";

/**
 * Props every wizard step content component receives from {@link SetupWizard}.
 *
 * A step is "run" by calling `onRun`, which posts `setup:start { step }` to the
 * host. Progress then flows back through `setup:progress` (or, in a plain
 * browser with no host, is simulated) and lands in `status`/`detail`.
 */
export interface StepProps {
  /** Latest `deps:status` snapshot (real detection when hosted). */
  deps: DepsStatus;
  /** Live state of this step, driven by `setup:progress`. */
  status: SetupStepStatus;
  /** Optional human detail from `setup:progress.detail`. */
  detail?: string | undefined;
  /** True when running inside the WebView2 host (`window.chrome.webview`). */
  connected: boolean;
  /** Run this step: posts `setup:start` for it. */
  onRun: () => void;
}
