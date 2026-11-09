import { Crop, ExternalLink, MonitorPlay, SlidersHorizontal, WandSparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EDITOR_URL } from "@/lib/constants";

interface GuideStep {
  icon: LucideIcon;
  title: string;
  body: string;
}

const GUIDE_STEPS: GuideStep[] = [
  {
    icon: Crop,
    title: "Load a controller photo",
    body: "Drop a top-down screenshot of your controller. The editor uses it as the canvas for every widget.",
  },
  {
    icon: WandSparkles,
    title: "Place widgets",
    body: "Draw boxes over each knob, fader and button. Use AI Suggest to auto-detect, then nudge by hand.",
  },
  {
    icon: SlidersHorizontal,
    title: "Bind to MIDI",
    body: "Each box is bound to a channel/CC pair so the overlay highlights exactly the control that moved.",
  },
];

export function Editor() {
  const [url, setUrl] = useState(EDITOR_URL);

  return (
    <>
      <section className="rounded-lg border bg-card p-6 shadow-card">
        <h2 className="text-lg font-semibold">How the editor works</h2>
        <div className="mt-5 grid gap-6 sm:grid-cols-3">
          {GUIDE_STEPS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex flex-col gap-3">
              <span className="flex size-10 items-center justify-center rounded-md border bg-raised">
                <Icon className="size-5 text-foreground" strokeWidth={1.75} />
              </span>
              <h3 className="text-base font-semibold">{title}</h3>
              <p className="text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Visual editor</h2>
        <div className="overflow-hidden rounded-lg border bg-card shadow-card">
          <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3">
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              spellCheck={false}
              aria-label="Editor URL"
              className="min-w-0 flex-1 rounded-md border bg-background px-3 py-1.5 font-mono text-xs text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-1 focus-visible:ring-ring"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
            >
              <ExternalLink /> Open in browser
            </Button>
          </div>
          <div className="flex h-[460px] flex-col items-center justify-center gap-4 bg-inset px-6 text-center">
            <span className="flex size-12 items-center justify-center rounded-md border bg-raised">
              <MonitorPlay className="size-6 text-primary" strokeWidth={1.75} />
            </span>
            <p className="text-base font-semibold">Embedded editor placeholder</p>
            <p className="max-w-md text-sm text-muted-foreground">
              Wiring later: this region embeds the existing overlay editor served by the Python
              sidecar. Until then, use “Open in browser” once the sidecar is running on :8080.
            </p>
            <p className="font-mono text-xs text-muted-foreground">{EDITOR_URL}</p>
          </div>
        </div>
      </section>
    </>
  );
}
