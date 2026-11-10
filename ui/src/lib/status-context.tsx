import { createContext, useContext } from "react";

import type { LogLine } from "@/components/midimat/server-log";
import type { MidiMatConfig } from "./ipc";

/**
 * Server settings the Status switches can toggle. Keys are camelCase to match the
 * `config:save` payload; `App.tsx` maps them onto the snake_case config fields.
 */
export interface ServerFlagsPatch {
  demoMode?: boolean;
  nhlMode?: boolean;
  autoStart?: boolean;
}

/**
 * App-level data the Status screen consumes. `App.tsx` owns it (not the screen)
 * because the shell streams `server:log` continuously from startup — a screen that
 * only subscribes on mount loses every line posted before it appears. App also
 * caches the last `config:loaded` snapshot and writes flag changes straight back
 * over IPC, so the switches reflect persisted config.
 */
export interface StatusContextValue {
  /** Bounded, newest-last server log (already mapped to display rows). */
  log: LogLine[];
  /** Clear the App-level log buffer. */
  clearLog: () => void;
  /** Last `config:loaded` snapshot, or null before the shell has sent one. */
  config: MidiMatConfig | null;
  /** Optimistically update a server flag and persist it via `config:save`. */
  saveServerFlags: (patch: ServerFlagsPatch) => void;
}

export const StatusContext = createContext<StatusContextValue | null>(null);

export function useStatus(): StatusContextValue {
  const ctx = useContext(StatusContext);
  if (!ctx) {
    throw new Error("useStatus() must be used inside <StatusContext.Provider> (see App.tsx)");
  }
  return ctx;
}
