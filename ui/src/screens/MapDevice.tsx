import { Crosshair, Radio, Save, Usb } from "lucide-react";
import type { ComponentType } from "react";
import { useState } from "react";

import { GlowingCard, PulseDot } from "../components/ui";
import { cn } from "../lib/cn";

interface Step {
  icon: ComponentType<{ size?: number | string; className?: string }>;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    icon: Usb,
    title: "Connect the controller",
    body: "Plug in the NI controller and confirm it appears in the MIDI port list.",
  },
  {
    icon: Radio,
    title: "Arm signal capture",
    body: "Start listening on the MidiMAT loopMIDI port. Move one control at a time.",
  },
  {
    icon: Crosshair,
    title: "Match the control",
    body: "We show the incoming channel/CC. Pick the matching widget on your controller photo.",
  },
  {
    icon: Save,
    title: "Assign and save",
    body: "Write the mapping to controls.csv so the overlay knows what to highlight.",
  },
];

const PLACEHOLDER_SIGNALS = [
  "ch=1  cc=16  val=064  ·  hold  3ms",
  "ch=1  cc=17  val=127  ·  rise",
  "ch=2  cc=02  val=090  ·  fall",
  "ch=1  cc=48  val=127  ·  press",
];

export function MapDevice() {
  const [capturing, setCapturing] = useState(false);

  return (
    <div className="mm-scroll h-full overflow-y-auto px-8 py-7">
      <header className="mb-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Map New Device
        </h1>
        <p className="mt-1 max-w-2xl text-[13px] text-text-dim">
          Teach MidiMAT about a controller it has never seen before &mdash; four short steps.
        </p>
      </header>

      <div className="grid max-w-4xl grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Steps */}
        <ol className="flex flex-col gap-3">
          {STEPS.map(({ icon: Icon, title, body }, index) => (
            <li
              key={title}
              className="flex items-start gap-4 rounded-xl border border-border bg-bg-card p-4"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-bg-elevated font-mono text-xs text-accent">
                {index + 1}
              </div>
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-text">
                  <Icon size={15} className="text-text-dim" />
                  {title}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-text-dim">{body}</p>
              </div>
            </li>
          ))}
        </ol>

        {/* Live signal capture */}
        <div>
          <GlowingCard glow className="p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PulseDot status={capturing ? "running" : "idle"} label="Capture state" />
                <span className="text-sm font-medium text-text">
                  {capturing ? "Capturing…" : "Signal capture"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setCapturing((prev) => !prev)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                  capturing
                    ? "border-error/40 bg-error/15 text-error hover:bg-error/25"
                    : "border-accent/40 bg-accent/15 text-accent hover:bg-accent/25",
                )}
              >
                {capturing ? "Stop" : "Start capture"}
              </button>
            </div>

            <div className="mm-scroll mt-4 h-52 overflow-y-auto rounded-lg border border-border bg-bg-primary p-4 font-mono text-xs leading-relaxed">
              {capturing ? (
                PLACEHOLDER_SIGNALS.map((line, index) => (
                  <div key={line} className="flex gap-3 text-text">
                    <span className="shrink-0 text-text-dim/70">14:33:{12 + index}</span>
                    <span>{line}</span>
                  </div>
                ))
              ) : (
                <span className="text-text-dim">
                  Move a control on the controller to see live MIDI here.
                </span>
              )}
            </div>

            <p className="mt-3 font-mono text-[11px] text-text-dim">
              Wiring later: subscribes to <span className="text-accent">ws://127.0.0.1:8787</span>.
            </p>
          </GlowingCard>
        </div>
      </div>
    </div>
  );
}
