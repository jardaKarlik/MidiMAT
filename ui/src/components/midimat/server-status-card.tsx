import { ExternalLink, RotateCw, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusDot } from "./status-dot";

interface ServerStatusCardProps {
  httpUrl: string;
  wsUrl: string;
  uptime: string;
  eventCount: number;
  // Optional handlers: the design's buttons are inert placeholders; MidiMAT
  // passes real IPC callbacks for them via the Status screen.
  onRestart?: () => void;
  onStop?: () => void;
  onOpenOverlay?: () => void;
}

const numberFormat = new Intl.NumberFormat("de-DE");

export function ServerStatusCard({
  httpUrl,
  wsUrl,
  uptime,
  eventCount,
  onRestart,
  onStop,
  onOpenOverlay,
}: ServerStatusCardProps) {
  return (
    <section className="glow-breathe rounded-lg bg-card p-7">
      <div className="flex flex-wrap gap-8">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <StatusDot tone="success" size="lg" pulsing />
            <h2 className="text-2xl font-semibold">Running</h2>
          </div>
          <p className="mt-5 font-mono text-base text-primary">{httpUrl}</p>
          <p className="mt-2 font-mono text-base text-primary">{wsUrl}</p>
        </div>
        <dl className="space-y-4 border-l pl-8">
          <div>
            <dt className="text-sm text-muted-foreground">Uptime</dt>
            <dd className="mt-1 font-mono text-lg">{uptime}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Events received</dt>
            <dd className="mt-1 font-mono text-lg">{numberFormat.format(eventCount)}</dd>
          </div>
        </dl>
      </div>
      <div className="mt-7 flex flex-wrap gap-3">
        <Button variant="outline" onClick={onRestart}>
          <RotateCw /> Restart server
        </Button>
        <Button variant="outline" onClick={onStop}>
          <Square /> Stop
        </Button>
        <Button variant="outline" onClick={onOpenOverlay}>
          <ExternalLink /> Open overlay
        </Button>
      </div>
    </section>
  );
}
