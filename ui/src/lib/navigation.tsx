import { createContext, useContext } from "react";

import type { PageId } from "./ipc";

/**
 * The design drives navigation with TanStack Router `Link`s. MidiMAT has no
 * router: the native shell sends `navigate {page}` over IPC and the tags are
 * plain state. This context is the drop-in replacement the sidebar consumes,
 * so `app-sidebar.tsx` keeps its design markup and only swaps `Link` for a
 * callback.
 */
export interface NavContextValue {
  /** The page tag the shell/app is currently showing. */
  current: PageId;
  /** Show a page and echo the tag back to the shell. */
  navigate: (page: PageId) => void;
}

export const NavContext = createContext<NavContextValue | null>(null);

export function useNav(): NavContextValue {
  const ctx = useContext(NavContext);
  if (!ctx) {
    throw new Error("useNav() must be used inside <NavContext.Provider> (see App.tsx)");
  }
  return ctx;
}
