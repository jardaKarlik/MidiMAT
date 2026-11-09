import { createContext, useContext } from "react";

/**
 * Controls the first-run setup wizard overlay. `App.tsx` owns the open/close
 * state (so it can also auto-open when no setup state is persisted) and exposes
 * it here so screens — e.g. Setup Summary's "Re-run setup" — can trigger it.
 */
export interface SetupWizardContextValue {
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

export const SetupWizardContext = createContext<SetupWizardContextValue | null>(null);

export function useSetupWizard(): SetupWizardContextValue {
  const ctx = useContext(SetupWizardContext);
  if (!ctx) {
    throw new Error("useSetupWizard() must be used inside <SetupWizardContext.Provider> (see App.tsx)");
  }
  return ctx;
}
