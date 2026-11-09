import { Activity, CircleQuestionMark, House, LifeBuoy, Plus, Settings, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { COFFEE_URL } from "@/lib/constants";
import type { PageId } from "@/lib/ipc";
import { useNav } from "@/lib/navigation";
import { MidiMatLogo, MidiMatWordmark } from "./midimat-logo";

interface NavItem {
  label: string;
  icon: LucideIcon;
  /** Page tag to show; omit for footer actions that are not pages. */
  page?: PageId;
  /** Action for non-page entries (Support, Settings). */
  onClick?: () => void;
}

const mainNav: NavItem[] = [
  { label: "Setup Summary", icon: House, page: "setup-summary" },
  { label: "Status", icon: Activity, page: "status" },
  { label: "Editor", icon: SlidersHorizontal, page: "editor" },
  { label: "Map New Device", icon: Plus, page: "map-new-device" },
  { label: "Help", icon: CircleQuestionMark, page: "help" },
];

const footerNav: NavItem[] = [
  {
    label: "Support",
    icon: LifeBuoy,
    onClick: () => window.open(COFFEE_URL, "_blank", "noopener,noreferrer"),
  },
  { label: "Settings", icon: Settings, onClick: () => console.info("[midimat:nav] Settings is not implemented in v1") },
];

const itemClass =
  "relative flex h-11 w-full items-center gap-3 rounded-r-md px-5 text-sm text-foreground/85 transition-colors hover:bg-raised/60 hover:text-foreground";

const activeClass =
  "bg-raised text-foreground [&>svg]:text-primary before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:rounded-full before:bg-primary";

// The design uses TanStack Router `Link`s; MidiMAT routes on IPC page tags, so
// each entry is a <button> that calls into the nav context. Markup/classes are
// otherwise identical to the design.
function NavEntry({ item }: { item: NavItem }) {
  const { current, navigate } = useNav();
  const Icon = item.icon;
  const active = item.page !== undefined && current === item.page;
  const className = cn(itemClass, active && activeClass);

  const content = (
    <>
      <Icon className="size-[18px] shrink-0" strokeWidth={1.75} />
      <span>{item.label}</span>
    </>
  );

  if (!item.page) {
    return (
      <button type="button" className={className} onClick={item.onClick}>
        {content}
      </button>
    );
  }

  return (
    <button
      type="button"
      className={className}
      aria-current={active ? "page" : undefined}
      onClick={() => navigate(item.page as PageId)}
    >
      {content}
    </button>
  );
}

export function AppSidebar() {
  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r bg-sidebar py-6 pr-2">
      <div className="mb-8 flex items-center gap-3 px-5">
        <MidiMatLogo />
        <MidiMatWordmark />
      </div>
      <nav className="flex flex-col gap-1" aria-label="Main">
        {mainNav.map((item) => (
          <NavEntry key={item.label} item={item} />
        ))}
      </nav>
      <div className="mx-5 mt-auto mb-3 border-t" />
      <nav className="flex flex-col gap-1" aria-label="Secondary">
        {footerNav.map((item) => (
          <NavEntry key={item.label} item={item} />
        ))}
      </nav>
    </aside>
  );
}
