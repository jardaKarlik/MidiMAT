import { Cable, Disc3, ExternalLink, RefreshCw, Server, Video } from "lucide-react";
import { useCallback, useState } from "react";

import { SetupCard, type SetupItem } from "@/components/midimat/setup-card";
import type { StatusTone } from "@/components/midimat/status-dot";
import { useSetupWizard } from "@/components/setup/setup-wizard-context";
import { Button } from "@/components/ui/button";
import { OVERLAY_URL } from "@/lib/constants";
import { ClientMessage, useHostMessages, type DepsStatus } from "@/lib/ipc";

type ComponentKey = "loopMidi" | "traktor" | "server" | "obs";

const CARD_ORDER: ComponentKey[] = ["loopMidi", "traktor", "server", "obs"];

// Only presentation lives here. Every path/value shown comes from the shell via
// `deps:status.detail` — never invent a machine-specific path client-side.
const META: Record<
  ComponentKey,
  { title: string; icon: SetupItem["icon"]; pathLabel: string; okState: string; fallbackDetail: string }
> = {
  loopMidi: {
    title: "loopMIDI",
    icon: Cable,
    pathLabel: "Port",
    okState: "Installed",
    fallbackDetail: "virtual MIDI port",
  },
  traktor: {
    title: "Traktor",
    icon: Disc3,
    pathLabel: "Config file",
    okState: "Configured",
    fallbackDetail: "settings file",
  },
  server: {
    title: "Server",
    icon: Server,
    pathLabel: "Config file",
    okState: "Running",
    fallbackDetail: ":8080 / :8787",
  },
  obs: {
    title: "OBS",
    icon: Video,
    pathLabel: "Install path",
    okState: "Detected",
    fallbackDetail: "Browser Source ready",
  },
};

const PORT_HINT = "MidiMAT";

function toneFor(key: ComponentKey, present: boolean): StatusTone {
  if (key === "obs") return "warning";
  if (key === "server") return present ? "success" : "warning";
  return present ? "success" : "error";
}

function buildItems(deps: DepsStatus): SetupItem[] {
  const d = deps.detail ?? {};

  const detailFor: Record<ComponentKey, string> = {
    loopMidi: d.port ? `port ${d.port}` : META.loopMidi.fallbackDetail,
    traktor: d.traktor && deps.traktor ? "settings file found" : META.traktor.fallbackDetail,
    server: META.server.fallbackDetail,
    obs: deps.obs ? "Browser Source ready" : META.obs.fallbackDetail,
  };

  const pathFor: Record<ComponentKey, string> = {
    // loopMIDI has no config file of its own — show the port it must define.
    loopMidi: d.port ?? PORT_HINT,
    traktor: d.traktor ?? "not found",
    server: d.server ?? "not found",
    obs: d.obs ?? "not found",
  };

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
      detail: detailFor[key],
      pathLabel: meta.pathLabel,
      path: pathFor[key],
    };
  });
}

export function SetupSummary() {
  const { open: openSetupWizard } = useSetupWizard();
  const [deps, setDeps] = useState<DepsStatus | null>(null);

  useHostMessages(
    useCallback((message) => {
      if (message.type === ClientMessage.DepsStatus) {
        setDeps(message.payload);
      }
    }, []),
  );

  // Until the shell reports, show every component as unknown rather than guessing.
  const items = buildItems(
    deps ?? { loopMidi: false, traktor: false, server: false, obs: false, python: false },
  );

  return (
    <>
      <div className="grid gap-5 md:grid-cols-2">
        {items.map((item) => (
          <SetupCard key={item.title} item={item} />
        ))}
      </div>
      <div className="mt-8 flex flex-wrap gap-4">
        <Button variant="outline" size="lg" onClick={openSetupWizard}>
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
