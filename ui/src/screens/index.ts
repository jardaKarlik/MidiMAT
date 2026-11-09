import type { ComponentType } from "react";

import type { PageId } from "../lib/ipc";
import { Editor } from "./Editor";
import { Help } from "./Help";
import { MapDevice } from "./MapDevice";
import { SetupSummary } from "./SetupSummary";
import { Status } from "./Status";

export interface PageDescriptor {
  title: string;
  subtitle: string;
  Component: ComponentType;
}

/**
 * Screen registry keyed by the same tags the native shell navigates with.
 * Each page carries the header text the design's AppShell renders.
 */
export const PAGES: Record<PageId, PageDescriptor> = {
  "setup-summary": {
    title: "Setup Summary",
    subtitle: "Check the status of your MidiMAT setup and connected components.",
    Component: SetupSummary,
  },
  status: {
    title: "Status",
    subtitle: "Monitor the server, MIDI connections and live activity.",
    Component: Status,
  },
  editor: {
    title: "Editor",
    subtitle: "Lay out the overlay by mapping controller controls to on-screen widgets.",
    Component: Editor,
  },
  "map-new-device": {
    title: "Map New Device",
    subtitle: "Teach MidiMAT about a controller it has never seen before — four short steps.",
    Component: MapDevice,
  },
  help: {
    title: "Help",
    subtitle: "How MidiMAT works, what the switches do, and where to find more.",
    Component: Help,
  },
};
