import { AnimatePresence } from "framer-motion";
import { useCallback, useMemo, useState } from "react";

import { AppShell } from "./components/midimat/app-shell";
import { PageTransition } from "./components/layout/PageTransition";
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
  type PageId,
  postToHost,
  useHostMessages,
} from "./lib/ipc";
import { NavContext, type NavContextValue } from "./lib/navigation";
import { PAGES } from "./screens";

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

  // The shell can drive navigation (tray menu, setup flow) using the same tags,
  // and tells us when there is no persisted setup state (open the wizard).
  const handleHostMessage = useCallback((message: HostInboundMessage) => {
    if (message.type === HostMessage.Navigate) {
      setPage(message.payload.page);
    } else if (message.type === ClientMessage.ConfigLoaded) {
      const config = message.payload;
      if (!config.setup_completed || config.skip_checks === false) {
        setWizardOpen(true);
      }
    } else if (message.type === ClientMessage.DepsStatus) {
      setDeps(message.payload);
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

  const nav = useMemo<NavContextValue>(() => ({ current: page, navigate }), [page, navigate]);

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
        <AppShell title={title} subtitle={subtitle}>
          <AnimatePresence mode="wait" initial={false}>
            <PageTransition pageKey={page}>
              <Component />
            </PageTransition>
          </AnimatePresence>
        </AppShell>
        {wizardOpen ? <SetupWizard onFinish={closeWizard} initialDeps={deps ?? undefined} /> : null}
      </SetupWizardContext.Provider>
    </NavContext.Provider>
  );
}
