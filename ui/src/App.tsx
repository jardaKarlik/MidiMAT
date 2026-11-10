import { AnimatePresence } from "framer-motion";
import { useCallback, useMemo, useState } from "react";

import { AppShell } from "./components/midimat/app-shell";
import { PageTransition } from "./components/layout/PageTransition";
import type { LogLine } from "./components/midimat/server-log";
import { SetupWizard } from "./components/setup/SetupWizard";
import {
  SetupWizardContext,
  type SetupWizardContextValue,
} from "./components/setup/setup-wizard-context";
import {
  ClientMessage,
  HostMessage,
  type DepsStatus,
  type HostInboundMessage,
  type LogLevel,
  type MidiMatConfig,
  type PageId,
  type ServerLogPayload,
  postToHost,
  useHostMessages,
} from "./lib/ipc";
import { NavContext, type NavContextValue } from "./lib/navigation";
import {
  StatusContext,
  type ServerFlagsPatch,
  type StatusContextValue,
} from "./lib/status-context";
import { PAGES } from "./screens";

/**
 * The server log lives in App (not the Status screen): the shell streams
 * `server:log` from startup, so a screen that only subscribes on mount would miss
 * every earlier line. Bounded to keep memory flat on a long-running app.
 */
const MAX_LOGS = 200;

const LEVEL_MAP: Record<LogLevel, LogLine["level"]> = {
  info: "INFO",
  debug: "INFO",
  warn: "WARN",
  error: "ERROR",
};

function toLogLine(payload: ServerLogPayload): LogLine {
  const parsed = new Date(payload.ts);
  const time = Number.isNaN(parsed.getTime())
    ? payload.ts
    : parsed.toLocaleTimeString([], { hour12: false });
  return { time, level: LEVEL_MAP[payload.level], message: payload.line };
}

export interface AppProps {
  /**
   * Open the setup wizard on first render. Defaults to `false`, so a plain
   * browser (Vite dev / preview) always shows the normal app and startup is
   * never hijacked. The host can also trigger the wizard at runtime by sending
   * `config:loaded` with no `setup_completed` or with `skip_checks: false`
   * (DESIGN_APP.md §4).
   */
  autoOpenSetupWizard?: boolean;
}

export function App({ autoOpenSetupWizard = false }: AppProps) {
  const [page, setPage] = useState<PageId>("setup-summary");
  const [wizardOpen, setWizardOpen] = useState(autoOpenSetupWizard);
  // Latest dependency snapshot. Kept here (not only in the screens) because the
  // shell sends it once, early; anything that mounts later would otherwise miss it.
  const [deps, setDeps] = useState<DepsStatus | null>(null);
  // Same reasoning for the server log: the shell streams it from startup, so we
  // buffer it here and hand it to Status, which no longer subscribes itself.
  const [log, setLog] = useState<LogLine[]>([]);
  // Last `config:loaded` snapshot, so the Status switches show persisted values.
  const [config, setConfig] = useState<MidiMatConfig | null>(null);

  // The shell can drive navigation (tray menu, setup flow) using the same tags,
  // and tells us when there is no persisted setup state (open the wizard).
  const handleHostMessage = useCallback((message: HostInboundMessage) => {
    if (message.type === HostMessage.Navigate) {
      setPage(message.payload.page);
    } else if (message.type === ClientMessage.ConfigLoaded) {
      setConfig(message.payload);
      if (!message.payload.setup_completed || message.payload.skip_checks === false) {
        setWizardOpen(true);
      }
    } else if (message.type === ClientMessage.DepsStatus) {
      setDeps(message.payload);
    } else if (message.type === ClientMessage.ServerLog) {
      setLog((prev) => {
        const next = [...prev, toLogLine(message.payload)];
        return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
      });
    }
  }, []);

  useHostMessages(handleHostMessage);

  const navigate = useCallback((next: PageId) => {
    setPage(next);
    // Tell the shell so its sidebar/tray state can mirror the web app.
    postToHost(HostMessage.Navigate, { page: next });
  }, []);

  const closeWizard = useCallback(() => {
    setWizardOpen(false);
    navigate("setup-summary");
  }, [navigate]);

  const clearLog = useCallback(() => setLog([]), []);

  // Toggle a server flag: reflect it optimistically (so the switch stays in sync
  // without a round-trip) and persist it over IPC. The shell restarts the sidecar
  // when a start-up flag (demo/nhl) actually changed.
  const saveServerFlags = useCallback((patch: ServerFlagsPatch) => {
    setConfig((prev) => {
      if (!prev) {
        return prev;
      }
      const server = { ...prev.server };
      if (patch.demoMode !== undefined) server.demo_mode = patch.demoMode;
      if (patch.nhlMode !== undefined) server.nhl_mode = patch.nhlMode;
      if (patch.autoStart !== undefined) server.auto_start = patch.autoStart;
      return { ...prev, server };
    });
    postToHost(HostMessage.ConfigSave, patch);
  }, []);

  const nav = useMemo<NavContextValue>(() => ({ current: page, navigate }), [page, navigate]);

  const status = useMemo<StatusContextValue>(
    () => ({ log, clearLog, config, saveServerFlags }),
    [log, clearLog, config, saveServerFlags],
  );

  const setupWizard = useMemo<SetupWizardContextValue>(
    () => ({
      isOpen: wizardOpen,
      open: () => setWizardOpen(true),
      close: () => setWizardOpen(false),
    }),
    [wizardOpen],
  );

  const { title, subtitle, Component } = PAGES[page];

  // The shell (sidebar + scroll area) is rendered once and stays mounted while
  // only the screen body cross-fades — so navigating never remounts the sidebar.
  // The setup wizard renders above it as a full-screen overlay.
  return (
    <NavContext.Provider value={nav}>
      <SetupWizardContext.Provider value={setupWizard}>
        <StatusContext.Provider value={status}>
          <AppShell title={title} subtitle={subtitle}>
            <AnimatePresence mode="wait" initial={false}>
              <PageTransition pageKey={page}>
                <Component />
              </PageTransition>
            </AnimatePresence>
          </AppShell>
          {wizardOpen ? <SetupWizard onFinish={closeWizard} initialDeps={deps ?? undefined} /> : null}
        </StatusContext.Provider>
      </SetupWizardContext.Provider>
    </NavContext.Provider>
  );
}
