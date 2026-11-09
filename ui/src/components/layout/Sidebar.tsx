import {
  Activity,
  CircleHelp,
  Coffee,
  LayoutDashboard,
  Settings,
  SlidersHorizontal,
  Usb,
} from "lucide-react";
import type { ComponentType } from "react";

import { COFFEE_URL } from "../../lib/constants";
import type { PageId } from "../../lib/ipc";
import { cn } from "../../lib/cn";

/** Structural icon type — avoids depending on a specific lucide type export. */
type IconComponent = ComponentType<{ size?: number | string; className?: string }>;

interface NavItem {
  id: PageId;
  label: string;
  icon: IconComponent;
}

const PRIMARY_NAV: NavItem[] = [
  { id: "setup-summary", label: "Setup Summary", icon: LayoutDashboard },
  { id: "status", label: "Status", icon: Activity },
  { id: "editor", label: "Editor", icon: SlidersHorizontal },
  { id: "map-new-device", label: "Map New Device", icon: Usb },
  { id: "help", label: "Help", icon: CircleHelp },
];

export interface SidebarProps {
  current: PageId;
  onNavigate: (page: PageId) => void;
}

export function Sidebar({ current, onNavigate }: SidebarProps) {
  return (
    <aside className="flex h-full w-[220px] shrink-0 flex-col border-r border-border bg-bg-card">
      {/* Logo slot — neutral placeholder mark; real brand asset is pending approval. */}
      <div className="flex h-14 items-center gap-2.5 px-4">
        <div
          className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-accent to-accent-2"
          aria-hidden="true"
        >
          <span className="h-2.5 w-2.5 rounded-[3px] bg-bg-primary" />
        </div>
        <span className="font-mono text-[15px] font-semibold tracking-wide">MidiMAT</span>
      </div>

      <nav className="mt-2 flex flex-1 flex-col gap-0.5 px-2">
        {PRIMARY_NAV.map(({ id, label, icon: Icon }) => {
          const active = current === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onNavigate(id)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors duration-150",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                active
                  ? "bg-bg-elevated text-text"
                  : "text-text-dim hover:bg-bg-elevated/60 hover:text-text",
              )}
            >
              {active && (
                <span
                  className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-accent"
                  aria-hidden="true"
                />
              )}
              <Icon
                size={16}
                className={cn(
                  "shrink-0 transition-colors",
                  active ? "text-accent" : "text-text-dim group-hover:text-text",
                )}
              />
              <span className="truncate">{label}</span>
            </button>
          );
        })}
      </nav>

      {/* Bottom group */}
      <div className="flex flex-col gap-0.5 border-t border-border px-2 py-2">
        <a
          href={COFFEE_URL}
          target="_blank"
          rel="noreferrer noopener"
          className="group flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-text-dim transition-colors duration-150 hover:bg-bg-elevated/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <Coffee size={16} className="shrink-0 text-text-dim group-hover:text-text" />
          <span className="truncate">Support</span>
        </a>
        <button
          type="button"
          onClick={() => console.info("[midimat:nav] Settings is not implemented in v1")}
          className="group flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-text-dim transition-colors duration-150 hover:bg-bg-elevated/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <Settings size={16} className="shrink-0 text-text-dim group-hover:text-text" />
          <span className="truncate">Settings</span>
        </button>
      </div>
    </aside>
  );
}
