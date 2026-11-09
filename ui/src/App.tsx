import { AnimatePresence } from "framer-motion";
import { useCallback, useMemo, useState } from "react";

import { AppShell } from "./components/midimat/app-shell";
import { PageTransition } from "./components/layout/PageTransition";
import { HostMessage, type HostInboundMessage, type PageId, postToHost, useHostMessages } from "./lib/ipc";
import { NavContext, type NavContextValue } from "./lib/navigation";
import { PAGES } from "./screens";

export function App() {
  const [page, setPage] = useState<PageId>("setup-summary");

  // The shell can drive navigation (tray menu, setup flow) using the same tags.
  const handleHostMessage = useCallback((message: HostInboundMessage) => {
    if (message.type === HostMessage.Navigate) {
      setPage(message.payload.page);
    }
    // Other inbound messages (deps:status, server:log, …) are consumed by the
    // screens that care about them, via their own useHostMessages() subscription.
  }, []);

  useHostMessages(handleHostMessage);

  const navigate = useCallback((next: PageId) => {
    setPage(next);
    // Tell the shell so its sidebar/tray state can mirror the web app.
    postToHost(HostMessage.Navigate, { page: next });
  }, []);

  const nav = useMemo<NavContextValue>(() => ({ current: page, navigate }), [page, navigate]);

  const { title, subtitle, Component } = PAGES[page];

  // The shell (sidebar + scroll area) is rendered once and stays mounted while
  // only the screen body cross-fades — so navigating never remounts the sidebar.
  return (
    <NavContext.Provider value={nav}>
      <AppShell title={title} subtitle={subtitle}>
        <AnimatePresence mode="wait" initial={false}>
          <PageTransition pageKey={page}>
            <Component />
          </PageTransition>
        </AnimatePresence>
      </AppShell>
    </NavContext.Provider>
  );
}
