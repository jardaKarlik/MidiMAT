import { AnimatePresence } from "framer-motion";
import { useCallback, useState } from "react";

import { PageTransition } from "./components/layout/PageTransition";
import { Sidebar } from "./components/layout/Sidebar";
import { HostMessage, type HostInboundMessage, type PageId, postToHost, useHostMessages } from "./lib/ipc";
import { SCREENS } from "./screens";

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

  const Screen = SCREENS[page];

  return (
    <div className="flex h-full w-full overflow-hidden bg-bg-primary text-text">
      <Sidebar current={page} onNavigate={navigate} />
      <main className="relative flex-1 overflow-hidden">
        <AnimatePresence mode="wait" initial={false}>
          <PageTransition pageKey={page}>
            <Screen />
          </PageTransition>
        </AnimatePresence>
      </main>
    </div>
  );
}
