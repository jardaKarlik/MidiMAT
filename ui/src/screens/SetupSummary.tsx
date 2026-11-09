import { Cable, Disc3, ExternalLink, RefreshCw, Server, Video } from "lucide-react";
import { useCallback, useState } from "react";

import { SetupCard, type SetupItem } from "@/components/midimat/setup-card";
import type { StatusTone } from "@/components/midimat/status-dot";
import { Button } from "@/components/ui/button";
import { OVERLAY_URL } from "@/lib/constants";
import { ClientMessage, HostMessage, postToHost, useHostMessages, type DepsStatus } from "@/lib/ipc";

type ComponentKey = "loopMidi" | "traktor" | "server" | "obs";

const CARD_ORDER: ComponentKey[] = ["loopMidi", "traktor", "server", "obs"];

// Static presentation (titles, details, example paths) is the design's; only the
// tone/state come from live `deps:status` data.
const META: Record<
  ComponentKey,
  { title: string; icon: SetupItem["icon"]; detail: string; path: string; okState: string }
> = {
  loopMidi: {
    title: "loopMIDI",
    icon: Cable,
    detail: "port MidiMAT",
    path: "C:\\Users\\You\\AppData\\Roaming\\MidiMAT\\loopmidi.json",
    okState: "Installed",
  },
  traktor: {
    title: "Traktor",
    icon: Disc3,
    detail: "TSI v4.5.1",
    path: "C:\\Users\\You\\Documents\\Native Instruments\\Traktor\\MidiMAT.tsi",
    okState: "Configured",
  },
  server: {
    title: "Server",
    icon: Server,
    detail: ":8080 / :8787",
    path: "C:\\Users\\You\\AppData\\Roaming\\MidiMAT\\server.json",
    okState: "Running",
  },
  obs: {
    title: "OBS",
    icon: Video,
    detail: "Browser Source ready",
    path: "C:\\Users\\You\\AppData\\Roaming\\obs-studio\\basic\\scenes",
    okState: "Detected",
  },
};

// Reproduces the design's default presentation until the shell pushes real data.
const PLACEHOLDER_DEPS: DepsStatus = {
  loopMidi: true,
  traktor: true,
  server: true,
  obs: true,
  python: true,
};

function toneFor(key: ComponentKey, present: boolean): StatusTone {
  if (key === "obs") return "warning";
  if (key === "server") return present ? "success" : "warning";
  return present ? "success" : "error";
}

function buildItems(deps: DepsStatus): SetupItem[] {
  return CARD_ORDER.map((key) => {
    const present = deps[key];
    const meta = META[key];
    const state = present ? meta.okState : key === "server" ? "Starting…" : "Not detected";
    return {
      title: meta.title,
      icon: meta.icon,
      tone: toneFor(key, present),
      pulsing: key === "server" && present,
      state,
      detail: meta.detail,
      path: meta.path,
    };
  });
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

  const items = buildItems(deps);

  return (
    <>
      <div className="grid gap-5 md:grid-cols-2">
        {items.map((item) => (
          <SetupCard key={item.title} item={item} />
        ))}
      </div>
      <div className="mt-8 flex flex-wrap gap-4">
        <Button variant="outline" size="lg" onClick={() => postToHost(HostMessage.SetupStart, { step: 1 })}>
          <RefreshCw /> Re-run setup
        </Button>
        <Button
          variant="outline"
          size="lg"
          onClick={() => window.open(OVERLAY_URL, "_blank", "noopener,noreferrer")}
        >
          <ExternalLink /> Open overlay URL
        </Button>
      </div>
    </>
  );
}
