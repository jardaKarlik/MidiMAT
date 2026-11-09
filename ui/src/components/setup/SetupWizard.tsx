import {
  ArrowLeft,
  ArrowRight,
  Check,
  LoaderCircle,
  TriangleExclamationPoint,
  X,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { MidiMatLogo } from "@/components/midimat/midimat-logo";
import { Button } from "@/components/ui/button";
import {
  ClientMessage,
  HostMessage,
  hasHostBridge,
  postToHost,
  useHostMessages,
  type DepsStatus,
  type SetupStepStatus,
} from "@/lib/ipc";
import { cn } from "@/lib/utils";
import { StepLoopMidi } from "./StepLoopMidi";
import { StepObs } from "./StepObs";
import { StepRuntime } from "./StepRuntime";
import { StepSave } from "./StepSave";
import { StepServer } from "./StepServer";
import { StepTraktor } from "./StepTraktor";
import type { StepProps } from "./types";
import { FIRST_STEP, LAST_STEP, WIZARD_STEPS } from "./wizard-steps";

interface StepState {
  status: SetupStepStatus;
  detail?: string | undefined;
}

const NO_DEPS: DepsStatus = {
  loopMidi: false,
  traktor: false,
  obs: false,
  python: false,
  server: false,
};

/** How long the browser-preview "simulation" runs before a step reports done. */
const SIMULATED_STEP_MS = 800;

function initialStates(): Record<number, StepState> {
  const result: Record<number, StepState> = {};
  for (const step of WIZARD_STEPS) {
    result[step.id] = { status: "pending" };
  }
  return result;
}

const CIRCLE_STATE: Record<SetupStepStatus, string> = {
  pending: "border-border bg-raised text-muted-foreground",
  running: "border-primary bg-primary/10 text-primary",
  done: "border-success/50 bg-success/10 text-success",
  error: "border-destructive/50 bg-destructive/10 text-destructive",
};

export interface SetupWizardProps {
  /** Called when the user finishes (or dismisses) the wizard. */
  onFinish: () => void;
  /**
   * The latest `deps:status` the shell already sent (App keeps this). The wizard
   * mounts *after* that message, so without this every step would show
   * "not detected" until the next update arrives.
   */
  initialDeps?: DepsStatus | undefined;
}

/**
 * The first-run setup wizard (DESIGN_APP.md §4): a horizontal 6-step stepper
 * with the current step's content in a card below.
 *
 * Step lifecycle: clicking a step's primary action posts `setup:start { step }`
 * and marks it "running"; the host answers with `setup:progress { step, status,
 * detail }`, and the wizard echoes `setup:complete { step }` when it lands on
 * "done". `deps:status` keeps each step's real detection in sync. In a plain
 * browser (no `window.chrome.webview`) the actions are simulated so the whole
 * flow remains navigable.
 */
export function SetupWizard({ onFinish, initialDeps }: SetupWizardProps) {
  const connected = useMemo(() => hasHostBridge(), []);
  const [current, setCurrent] = useState<number>(FIRST_STEP);
  const [deps, setDeps] = useState<DepsStatus>(initialDeps ?? NO_DEPS);
  const [states, setStates] = useState<Record<number, StepState>>(initialStates);

  const completed = useRef<Set<number>>(new Set());
  const finishAfter = useRef<Set<number>>(new Set());
  const timers = useRef<number[]>([]);

  useEffect(
    () => () => {
      for (const timer of timers.current) window.clearTimeout(timer);
    },
    [],
  );

  const completeStep = useCallback(
    (step: number, detail?: string) => {
      setStates((prev) => ({ ...prev, [step]: { status: "done", detail: detail ?? prev[step]?.detail } }));
      if (!completed.current.has(step)) {
        completed.current.add(step);
        postToHost(HostMessage.SetupComplete, { step });
      }
      if (finishAfter.current.has(step)) {
        finishAfter.current.delete(step);
        onFinish();
      }
    },
    [onFinish],
  );

  const runStep = useCallback(
    (step: number) => {
      completed.current.delete(step);
      setStates((prev) => ({ ...prev, [step]: { status: "running" } }));
      postToHost(HostMessage.SetupStart, { step });
      if (step === LAST_STEP) finishAfter.current.add(step);

      if (!connected) {
        const timer = window.setTimeout(
          () => completeStep(step, "Simulated — not connected to the MidiMAT host."),
          SIMULATED_STEP_MS,
        );
        timers.current.push(timer);
      }
    },
    [connected, completeStep],
  );

  useHostMessages(
    useCallback(
      (message) => {
        if (message.type === ClientMessage.DepsStatus) {
          setDeps(message.payload);
          return;
        }

        if (message.type === ClientMessage.SetupProgress) {
          const { step, status, detail } = message.payload;
          setStates((prev) => ({ ...prev, [step]: { status, detail } }));
          if (status === "done") {
            completeStep(step, detail);
          } else if (status === "error") {
            finishAfter.current.delete(step);
          }
        }
      },
      [completeStep],
    ),
  );

  const goNext = useCallback(() => {
    setCurrent((value) => (value >= LAST_STEP ? value : value + 1));
  }, []);
  const goBack = useCallback(() => {
    setCurrent((value) => Math.max(FIRST_STEP, value - 1));
  }, []);
  const runCurrent = useCallback(() => runStep(current), [runStep, current]);

  const stepState = states[current] ?? { status: "pending" as SetupStepStatus };
  const stepProps: StepProps = {
    deps,
    status: stepState.status,
    detail: stepState.detail,
    connected,
    onRun: runCurrent,
  };

  let content: ReactNode;
  switch (current) {
    case 1:
      content = <StepLoopMidi {...stepProps} />;
      break;
    case 2:
      content = <StepTraktor {...stepProps} />;
      break;
    case 3:
      content = <StepRuntime {...stepProps} />;
      break;
    case 4:
      content = <StepServer {...stepProps} />;
      break;
    case 5:
      content = <StepObs {...stepProps} />;
      break;
    default:
      content = <StepSave {...stepProps} />;
  }

  const isLast = current >= LAST_STEP;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-background"
      role="dialog"
      aria-modal="true"
      aria-label="MidiMAT setup wizard"
    >
      <header className="flex shrink-0 items-center justify-between border-b px-10 py-5">
        <div className="flex items-center gap-3">
          <MidiMatLogo />
          <div>
            <p className="text-sm font-semibold">Setup Wizard</p>
            <p className="text-xs text-muted-foreground">
              Step {current} of {LAST_STEP}
            </p>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onFinish} aria-label="Close setup wizard">
          <X />
        </Button>
      </header>

      <div className="shrink-0 border-b px-10 py-6">
        <div className="mx-auto max-w-[880px]">
          <WizardStepper current={current} states={states} onSelect={setCurrent} />
        </div>
      </div>

      <main className="min-h-0 flex-1 overflow-y-auto px-10 py-8">
        <div className="mx-auto max-w-[880px]">
          {content}

          <div className="mt-8 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={goBack} disabled={current <= FIRST_STEP}>
                <ArrowLeft /> Back
              </Button>
              {!isLast ? (
                <Button variant="ghost" onClick={goNext}>
                  Skip
                </Button>
              ) : null}
            </div>
            <Button onClick={isLast ? onFinish : goNext}>
              {isLast ? (
                "Finish"
              ) : (
                <>
                  Next <ArrowRight />
                </>
              )}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}

interface WizardStepperProps {
  current: number;
  states: Record<number, StepState>;
  onSelect: (step: number) => void;
}

function WizardStepper({ current, states, onSelect }: WizardStepperProps) {
  return (
    <div className="mm-scroll flex items-start overflow-x-auto pb-1" role="list">
      {WIZARD_STEPS.map((meta, index) => {
        const previous = index > 0 ? WIZARD_STEPS[index - 1] : undefined;
        const previousDone = previous ? states[previous.id]?.status === "done" : false;
        return (
          <Fragment key={meta.id}>
            {previous ? (
              <span
                aria-hidden="true"
                className={cn("mx-1 mt-5 h-px min-w-4 flex-1", previousDone ? "bg-success/60" : "bg-border")}
              />
            ) : null}
            <StepNode
              meta={meta}
              state={states[meta.id]?.status ?? "pending"}
              isCurrent={current === meta.id}
              onSelect={() => onSelect(meta.id)}
            />
          </Fragment>
        );
      })}
    </div>
  );
}

interface StepNodeProps {
  meta: (typeof WIZARD_STEPS)[number];
  state: SetupStepStatus;
  isCurrent: boolean;
  onSelect: () => void;
}

function StepNode({ meta, state, isCurrent, onSelect }: StepNodeProps) {
  const Icon = meta.icon;
  return (
    <button
      type="button"
      role="listitem"
      onClick={onSelect}
      aria-current={isCurrent ? "step" : undefined}
      className="flex w-[76px] shrink-0 flex-col items-center gap-2 rounded-md focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    >
      <span
        className={cn(
          "flex size-10 items-center justify-center rounded-full border transition-colors",
          CIRCLE_STATE[state],
          isCurrent && "ring-2 ring-primary/40",
        )}
      >
        {state === "running" ? (
          <LoaderCircle className="size-5 animate-spin" />
        ) : state === "done" ? (
          <Check className="size-5" />
        ) : state === "error" ? (
          <TriangleExclamationPoint className="size-5" />
        ) : (
          <Icon className="size-5" strokeWidth={1.75} />
        )}
      </span>
      <span className={cn("text-center text-xs", isCurrent ? "text-foreground" : "text-muted-foreground")}>
        {meta.label}
      </span>
    </button>
  );
}
