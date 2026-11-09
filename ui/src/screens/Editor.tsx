import { Crop, ExternalLink, RefreshCw, Wand2 } from "lucide-react";
import type { ComponentType } from "react";
import { useState } from "react";

import { AnimatedBorder, GlowingCard } from "../components/ui";
import { EDITOR_URL } from "../lib/constants";

interface GuideStep {
  icon: ComponentType<{ size?: number | string; className?: string }>;
  title: string;
  body: string;
}

const GUIDE_STEPS: GuideStep[] = [
  {
    icon: Crop,
    title: "1 · Load the controller photo",
    body: "Drop a top-down screenshot of your controller. The editor uses it as the canvas for every widget.",
  },
  {
    icon: Wand2,
    title: "2 · Place widgets",
    body: "Draw boxes over each knob, fader and button. Use AI Suggest to auto-detect, then nudge by hand.",
  },
  {
    icon: Crop,
    title: "3 · Bind to MIDI",
    body: "Each box is bound to a channel/CC pair so the overlay highlights exactly the control that moved.",
  },
];

export function Editor() {
  const [url, setUrl] = useState(EDITOR_URL);
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <div className="mm-scroll h-full overflow-y-auto px-8 py-7">
      <header className="mb-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Editor
        </h1>
        <p className="mt-1 max-w-2xl text-[13px] text-text-dim">
          Lay out the overlay by mapping controller controls to on-screen widgets.
        </p>
      </header>

      {/* Guidance panel */}
      <AnimatedBorder className="max-w-3xl" active>
        <div className="p-6">
          <h2 className="text-sm font-semibold text-text">How the editor works</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {GUIDE_STEPS.map(({ icon: Icon, title, body }) => (
              <div key={title} className="flex flex-col gap-2">
                <Icon size={18} className="text-accent" />
                <div className="text-[13px] font-medium text-text">{title}</div>
                <p className="text-xs leading-relaxed text-text-dim">{body}</p>
              </div>
            ))}
          </div>
          <p className="mt-5 border-t border-border pt-4 font-mono text-[11px] text-text-dim">
            Wiring later: this screen will embed the existing{" "}
            <span className="text-accent">overlay/edit.html</span> served by the Python sidecar.
          </p>
        </div>
      </AnimatedBorder>

      {/* Embedded editor placeholder */}
      <section className="mt-8 max-w-3xl">
        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Visual Editor
        </h2>
        <GlowingCard className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-border bg-bg-elevated/50 px-3 py-2">
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              spellCheck={false}
              aria-label="Editor URL"
              className="min-w-0 flex-1 rounded-md border border-border bg-bg-primary px-2.5 py-1.5 font-mono text-xs text-text placeholder:text-text-dim focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
            />
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-bg-card px-2.5 py-1.5 text-xs text-text-dim transition-colors hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
            >
              <RefreshCw size={13} />
              Reload
            </button>
            <button
              type="button"
              onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-bg-card px-2.5 py-1.5 text-xs text-text-dim transition-colors hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
            >
              <ExternalLink size={13} />
              Open in browser
            </button>
          </div>

          <div className="relative h-[460px] bg-bg-primary">
            {/* Wiring later: the sidecar serves overlay/edit.html. Until it is
                running this shows the browser's connection error — expected. */}
            <iframe
              key={reloadKey}
              title="MidiMAT visual editor (overlay/edit.html)"
              src={url}
              className="h-full w-full border-0"
            />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center gap-2 border-t border-border bg-bg-card/90 px-3 py-2 text-[11px] text-text-dim backdrop-blur">
              Placeholder embed &mdash; requires the sidecar on :8080. Self-hosted routing note:
              the shell maps this page at https://midimat.local/, the editor at http://127.0.0.1:8080.
            </div>
          </div>
        </GlowingCard>
      </section>
    </div>
  );
}
