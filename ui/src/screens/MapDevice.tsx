import { Crosshair, Radio, Save, Usb } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";

import { StatusDot } from "@/components/midimat/status-dot";
import { Button } from "@/components/ui/button";

interface Step {
  icon: LucideIcon;
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
    <>
      <ol className="grid gap-5 md:grid-cols-2">
        {STEPS.map(({ icon: Icon, title, body }, index) => (
          <li key={title} className="rounded-lg border bg-card p-6 shadow-card">
            <div className="flex items-center justify-between gap-3">
              <span className="flex size-10 items-center justify-center rounded-md border bg-raised">
                <Icon className="size-5 text-foreground" strokeWidth={1.75} />
              </span>
              <span className="font-mono text-xs text-muted-foreground">Step {index + 1}</span>
            </div>
            <h2 className="mt-5 text-base font-semibold">{title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{body}</p>
          </li>
        ))}
      </ol>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Live signal capture</h2>
        <div className="rounded-lg border bg-card p-6 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="flex items-center gap-2.5 text-sm">
              <StatusDot tone={capturing ? "success" : "warning"} pulsing={capturing} />
              <span>{capturing ? "Capturing…" : "Idle"}</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">
                Move one control at a time to identify its channel/CC.
              </span>
            </p>
            <Button
              variant={capturing ? "destructive" : "default"}
              onClick={() => setCapturing((prev) => !prev)}
            >
              {capturing ? "Stop capture" : "Start capture"}
            </Button>
          </div>

          <div className="mm-scroll mt-5 h-52 overflow-y-auto rounded-md border bg-inset p-5 font-mono text-xs leading-6 text-muted-foreground">
            {capturing ? (
              PLACEHOLDER_SIGNALS.map((line, index) => (
                <p key={line} className="flex gap-4 whitespace-pre-wrap">
                  <span>14:33:{12 + index}</span>
                  <span className="min-w-0 break-all">{line}</span>
                </p>
              ))
            ) : (
              <p>Move a control on the controller to see live MIDI here.</p>
            )}
          </div>

          <p className="mt-3 font-mono text-xs text-muted-foreground">
            Wiring later: subscribes to ws://127.0.0.1:8787 for live MIDI events.
          </p>
        </div>
      </section>
    </>
  );
}
