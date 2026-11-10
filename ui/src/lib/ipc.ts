import { useEffect, useRef } from "react";

/* ===========================================================================
 * IPC protocol (DESIGN_APP.md §3.1).
 *
 * These string literals are a 1:1 mirror of `IpcMessageTypes` in
 * app/Services/IpcBridge.cs. Do not rename them on one side only — the C#
 * switch and the TypeScript switch must stay in lockstep.
 * ======================================================================== */

/** Message types the page posts to the host (React → C#). */
export const HostMessage = {
  Navigate: "navigate",
  SetupStart: "setup:start",
  SetupComplete: "setup:complete",
  ServerRestart: "server:restart",
  ServerStop: "server:stop",
  ConfigSave: "config:save",
} as const;

/** Message types the host posts to the page (C# → React). */
export const ClientMessage = {
  DepsStatus: "deps:status",
  ServerLog: "server:log",
  SetupProgress: "setup:progress",
  ConfigLoaded: "config:loaded",
} as const;

export type HostMessageType = (typeof HostMessage)[keyof typeof HostMessage];
export type ClientMessageType = (typeof ClientMessage)[keyof typeof ClientMessage];

/** Screens the shell can ask us to show, keyed by the same tag it sends. */
export type PageId = "setup-summary" | "status" | "editor" | "map-new-device" | "help";

/* ---- JSON shapes (mirroring DESIGN_APP.md §3.1 + §6) --------------------- */

export interface DepsStatus {
  loopMidi: boolean;
  traktor: boolean;
  obs: boolean;
  python: boolean;
  server: boolean;
  /**
   * Real, machine-specific values supplied by the shell (paths, versions, the
   * sidecar launch description). Optional so the UI still works if an older
   * shell doesn't send it — but never invent these client-side.
   */
  detail?: DepsStatusDetail | undefined;
}

export interface DepsStatusDetail {
  /** e.g. "installed · v1.0.16.27" */
  loopMidi?: string;
  /** the real `Traktor Settings.tsi` path when found */
  traktor?: string;
  /** the OBS install path / registry detail */
  obs?: string;
  /** how the sidecar runtime resolves (bundled exe, or python + server.py) */
  runtime?: string;
  /** the MidiMAT config file path */
  server?: string;
  /** the virtual MIDI port name (e.g. "MidiMAT") */
  port?: string;
}

export type LogLevel = "info" | "warn" | "error" | "debug";

export interface ServerLogPayload {
  line: string;
  level: LogLevel;
  /** ISO-8601 timestamp supplied by the shell (see §3.1/§3.3). */
  ts: string;
}

export type SetupStepStatus = "pending" | "running" | "done" | "error";

export interface SetupProgressPayload {
  step: number;
  status: SetupStepStatus;
  detail?: string;
}

/** midimat.config.json — see DESIGN_APP.md §6. */
export interface MidiMatConfig {
  version: number;
  setup_completed?: string | null;
  skip_checks: boolean;
  paths: {
    loopmidi_port: string;
    traktor_tsi: string;
    obs_exe: string | null;
  };
  server: {
    http_port: number;
    ws_port: number;
    auto_start: boolean;
    demo_mode: boolean;
    nhl_mode: boolean;
  };
  overlay_url?: string;
  editor_url?: string;
}

/** Payloads for every React → C# message. */
export interface OutboundPayloads {
  [HostMessage.Navigate]: { page: PageId };
  [HostMessage.SetupStart]: { step: number };
  [HostMessage.SetupComplete]: { step: number };
  [HostMessage.ServerRestart]: Record<string, never>;
  [HostMessage.ServerStop]: Record<string, never>;
  // Every field is optional: callers send only what changed. The wizard still
  // sends `{ skipChecks }`; the Status switches send demoMode/nhlMode/autoStart.
  [HostMessage.ConfigSave]: {
    skipChecks?: boolean;
    demoMode?: boolean;
    nhlMode?: boolean;
    autoStart?: boolean;
  };
}

/** Payloads for every C# → React message. */
export interface InboundPayloads {
  [ClientMessage.DepsStatus]: DepsStatus;
  [ClientMessage.ServerLog]: ServerLogPayload;
  [ClientMessage.SetupProgress]: SetupProgressPayload;
  [ClientMessage.ConfigLoaded]: MidiMatConfig;
}

/** Discriminated union of messages we send. */
export type HostOutboundMessage = {
  [K in HostMessageType]: { type: K; payload: OutboundPayloads[K] };
}[HostMessageType];

/**
 * Discriminated union of messages we receive.
 *
 * The documented C→R set lives in `InboundPayloads`. The shell additionally
 * drives navigation (tray menu, setup flow) by posting `navigate` with the same
 * page tags it uses for its own routing, so that member is included here too.
 */
export type HostInboundMessage =
  | {
      [K in ClientMessageType]: { type: K; payload: InboundPayloads[K] };
    }[ClientMessageType]
  | { type: typeof HostMessage.Navigate; payload: { page: PageId } };

/* ---- WebView2 host bridge surface ---------------------------------------- */

export interface WebView2MessageEvent {
  data: unknown;
}

export interface WebView2Host {
  postMessage(message: unknown): void;
  addEventListener(type: "message", listener: (event: WebView2MessageEvent) => void): void;
  removeEventListener(type: "message", listener: (event: WebView2MessageEvent) => void): void;
}

declare global {
  interface Window {
    /** Injected by WebView2 only when hosted in the MidiMAT shell. */
    chrome?: {
      webview?: WebView2Host;
    };
  }
}

/** True when running inside the WebView2 shell (false in a plain browser). */
export function hasHostBridge(): boolean {
  return typeof window !== "undefined" && !!window.chrome?.webview;
}

function getWebView(): WebView2Host | undefined {
  return typeof window !== "undefined" ? window.chrome?.webview : undefined;
}

/**
 * Post a typed message to the native host.
 *
 * Outside the shell (Vite dev server / a normal browser) `window.chrome.webview`
 * does not exist — this degrades to a console log and returns `false` rather
 * than throwing, so the UI stays fully usable in a browser.
 */
export function postToHost<T extends HostMessageType>(
  type: T,
  payload: OutboundPayloads[T],
): boolean {
  const webview = getWebView();

  if (!webview) {
    console.info(`[midimat:ipc] no host bridge — (browser) would post "${type}"`, payload);
    return false;
  }

  webview.postMessage({ type, payload });
  return true;
}

/**
 * Subscribe to messages from the native host. The handler is kept in a ref so
 * callers can pass an inline closure without re-subscribing on every render.
 *
 * Outside the shell this is a no-op (a single console note on mount).
 */
export function useHostMessages(handler: (message: HostInboundMessage) => void): void {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    const webview = getWebView();

    if (!webview) {
      console.info(
        "[midimat:ipc] host bridge unavailable — running outside the MidiMAT shell (browser dev mode).",
      );
      return;
    }

    const listener = (event: WebView2MessageEvent): void => {
      const data = event.data;
      if (data && typeof data === "object" && "type" in data) {
        handlerRef.current(data as HostInboundMessage);
      }
    };

    webview.addEventListener("message", listener);
    return () => webview.removeEventListener("message", listener);
  }, []);
}
