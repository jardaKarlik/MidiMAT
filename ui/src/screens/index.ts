import type { ComponentType } from "react";

import type { PageId } from "../lib/ipc";
import { Editor } from "./Editor";
import { Help } from "./Help";
import { MapDevice } from "./MapDevice";
import { SetupSummary } from "./SetupSummary";
import { Status } from "./Status";

/** Screen registry keyed by the same tags the native shell navigates with. */
export const SCREENS: Record<PageId, ComponentType> = {
  "setup-summary": SetupSummary,
  status: Status,
  editor: Editor,
  "map-new-device": MapDevice,
  help: Help,
};
