import type { LucideIcon } from "lucide-react";
import { StatusDot, type StatusTone } from "./status-dot";

export interface SetupItem {
  title: string;
  icon: LucideIcon;
  tone: StatusTone;
  pulsing?: boolean | undefined;
  state: string;
  detail: string;
  path: string;
}

export function SetupCard({ item }: { item: SetupItem }) {
  const Icon = item.icon;
  return (
    <article className="rounded-lg border bg-card p-6 shadow-card">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md border bg-raised">
          <Icon className="size-5 text-foreground" strokeWidth={1.75} />
        </span>
        <h2 className="text-base font-semibold">{item.title}</h2>
      </div>
      <p className="mt-5 flex items-center gap-2.5 text-sm">
        <StatusDot tone={item.tone} pulsing={item.pulsing} />
        <span>{item.state}</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-muted-foreground">{item.detail}</span>
      </p>
      <div className="mt-5 border-t pt-4">
        <p className="text-xs text-muted-foreground">Config file</p>
        <p className="mt-1 font-mono text-xs leading-relaxed break-all text-muted-foreground">{item.path}</p>
      </div>
    </article>
  );
}
