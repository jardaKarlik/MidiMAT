import { ExternalLink, Music2, RefreshCw, Server, SlidersHorizontal, Video } from "lucide-react";
import type { ComponentType } from "react";
import { useCallback, useState } from "react";

import { EvervaultCard, PulseDot, type PulseStatus } from "../components/ui";
import { OVERLAY_URL } from "../lib/constants";
import {
  ClientMessage,
  HostMessage,
  postToHost,
  useHostMessages,
  type DepsStatus,
} from "../lib/ipc";

type IconComponent = ComponentType<{ size?: number | string; className?: string }>;
// The four cards we render; a subset of DepsStatus (which also has `python`).
type ComponentKey = "loopMidi" | "traktor" | "server" | "obs";

const CARD_ORDER: ComponentKey[] = ["loopMidi", "traktor", "server", "obs"];

const META: Record<ComponentKey, { title: string; icon: IconComponent; detail: string }> = {
  loopMidi: { title: "loopMIDI", icon: Music2, detail: "Port: MidiMAT" },
  traktor: { title: "Traktor", icon: SlidersHorizontal, detail: "TSI: v4.5.1 · Generic MIDI" },
  server: { title: "Server", icon: Server, detail: ":8080 · ws :8787" },
  obs: { title: "OBS", icon: Video, detail: "Browser Source" },
};

const OK_LABEL: Partial<Record<ComponentKey, string>> = {
  loopMidi: "Installed",
  traktor: "Configured",
  obs: "Detected",
};

// Placeholder state until the shell pushes a real deps:status.
const PLACEHOLDER_DEPS: DepsStatus = {
  loopMidi: true,
  traktor: true,
  server: true,
  obs: false,
  python: true,
};

function describe(key: ComponentKey, deps: DepsStatus): { status: PulseStatus; state: string } {
  const present = deps[key];
  if (key === "server") {
    return present ? { status: "running", state: "Running" } : { status: "warn", state: "Starting…" };
  }
  return present
    ? { status: "running", state: OK_LABEL[key] ?? "Ready" }
    : { status: "idle", state: "Not detected" };
}

export function SetupSummary() {
  const [deps, setDeps] = useState<DepsStatus>(PLACEHOLDER_DEPS);

  useHostMessages(
    useCallback((message) => {
      if (message.type === ClientMessage.DepsStatus) {
        setDeps(message.payload);
      }
    }, []),
  );

  return (
    <div className="mm-scroll h-full overflow-y-auto px-8 py-7">
      <header className="mb-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Setup Summary
        </h1>
        <p className="mt-1 text-[13px] text-text-dim">
          Everything MidiMAT needs, at a glance. Re-run setup if a component drifts out of place.
        </p>
      </header>

      <div className="grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
        {CARD_ORDER.map((key) => {
          const { title, icon: Icon, detail } = META[key];
          const { status, state } = describe(key, deps);
          return (
            <EvervaultCard key={key} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <Icon size={18} className="text-text-dim" />
                  <span className="text-sm font-semibold text-text">{title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <PulseDot status={status} label={`${title}: ${state}`} />
                  <span className="text-xs text-text-dim">{state}</span>
                </div>
              </div>
              <p className="mt-4 font-mono text-xs text-text-dim">{detail}</p>
            </EvervaultCard>
          );
        })}
      </div>

      <div className="mt-7 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => postToHost(HostMessage.SetupStart, { step: 1 })}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-bg-elevated px-4 py-2 text-sm font-medium text-text transition-colors hover:border-accent/40 hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <RefreshCw size={15} />
          Re-run Setup
        </button>
        <button
          type="button"
          onClick={() => {
            window.open(OVERLAY_URL, "_blank", "noopener,noreferrer");
          }}
          className="inline-flex items-center gap-2 rounded-md bg-accent/15 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <ExternalLink size={15} />
          Open Overlay URL
        </button>
      </div>
    </div>
  );
}
