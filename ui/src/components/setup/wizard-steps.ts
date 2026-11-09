import { Cable, Cpu, Disc3, Save, Server, Video, type LucideIcon } from "lucide-react";

/**
 * The six wizard steps (DESIGN_APP.md §4). `label` is the short stepper caption;
 * `id` is the 1-based step number posted to the host.
 */
export interface WizardStepMeta {
  id: number;
  key: string;
  label: string;
  icon: LucideIcon;
}

export const WIZARD_STEPS: WizardStepMeta[] = [
  { id: 1, key: "loopmidi", label: "loopMIDI", icon: Cable },
  { id: 2, key: "traktor", label: "Traktor", icon: Disc3 },
  { id: 3, key: "runtime", label: "Runtime", icon: Cpu },
  { id: 4, key: "server", label: "Server", icon: Server },
  { id: 5, key: "obs", label: "OBS", icon: Video },
  { id: 6, key: "save", label: "Save", icon: Save },
];

export const FIRST_STEP = WIZARD_STEPS[0].id;
export const LAST_STEP = WIZARD_STEPS[WIZARD_STEPS.length - 1].id;
