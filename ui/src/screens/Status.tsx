import { ExternalLink, Gamepad2, Plug, Rocket, RotateCw, Square, Terminal } from "lucide-react";
import type { ComponentType } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PulseDot, Switch, WobbleCard } from "../components/ui";
import { OVERLAY_URL, HTTP_BASE, WS_URL } from "../lib/constants";
import {
  ClientMessage,
  HostMessage,
  postToHost,
  useHostMessages,
  type LogLevel,
  type ServerLogPayload,
} from "../lib/ipc";
import { cn } from "../lib/cn";

type IconComponent = ComponentType<{ size?: number | string; className?: string }>;

interface SwitchDef {
  id: "demo" | "nhl" | "autostart";
  label: string;
  icon: IconComponent;
  description: string;
  initial: boolean;
}

const SWITCH_DEFS: SwitchDef[] = [
  {
    id: "demo",
    label: "Demo Mode",
    icon: Gamepad2,
    description: "Generate fake MIDI events for testing the overlay without hardware.",
    initial: false,
  },
  {
    id: "nhl",
    label: "NHL Native Mode",
    icon: Plug,
    description:
      "Listen to HID reports from NI controllers in native Traktor mode (bypasses loopMIDI).",
    initial: true,
  },
  {
    id: "autostart",
    label: "Auto-start",
    icon: Rocket,
    description: "Launch the sidecar server automatically whenever MidiMAT starts.",
    initial: true,
  },
];

const SEED_LOGS: ServerLogPayload[] = [
  { ts: "14:32:01", level: "info", line: "overlay: http://127.0.0.1:8080/overlay/index.html" },
  { ts: "14:32:01", level: "info", line: "WebSocket ready on ws://127.0.0.1:8787" },
  { ts: "14:32:05", level: "info", line: "midi| connected: TRAKTOR X1 MK3" },
  { ts: "14:32:05", level: "info", line: "midi| connected: TRAKTOR Z1 MK2" },
  { ts: "14:33:12", level: "info", line: "midi| ch=1 cc=16 val=64" },
];

const MAX_LOGS = 200;

const LEVEL_COLOR: Record<LogLevel, string> = {
  info: "text-text-dim",
  debug: "text-text-dim/70",
  warn: "text-warn",
  error: "text-error",
};

function formatTimestamp(ts: string): string {
  const parsed = new Date(ts);
  return Number.isNaN(parsed.getTime())
    ? ts
    : parsed.toLocaleTimeString([], { hour12: false });
}

export function Status() {
  const [switches, setSwitches] = useState<Record<SwitchDef["id"], boolean>>({
    demo: false,
    nhl: true,
    autostart: true,
  });
  const [logs, setLogs] = useState<ServerLogPayload[]>(SEED_LOGS);
  const logEndRef = useRef<HTMLDivElement>(null);

  useHostMessages(
    useCallback((message) => {
      if (message.type === ClientMessage.ServerLog) {
        setLogs((prev) => {
          const next = [...prev, message.payload];
          return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
        });
      }
    }, []),
  );

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" });
  }, [logs]);

  // Placeholder: the shell has not pushed a real health status yet, so we render
  // the "running" presentation from DESIGN_APP.md §8.2.
  const running = true;

  return (
    <div className="mm-scroll h-full overflow-y-auto px-8 py-7">
      <header className="mb-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Server Status
        </h1>
      </header>

      {/* Prominent server card */}
      <WobbleCard active={running} className="max-w-3xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <PulseDot status={running ? "running" : "idle"} size={12} label="Server status" />
            <span className="text-lg font-semibold">
              {running ? "Running" : "Stopped"}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ActionButton
              icon={RotateCw}
              label="Restart Server"
              onClick={() => postToHost(HostMessage.ServerRestart, {})}
            />
            <ActionButton
              icon={Square}
              label="Stop"
              onClick={() => postToHost(HostMessage.ServerStop, {})}
            />
            <ActionButton
              icon={ExternalLink}
              label="Open Overlay"
              tone="accent"
              onClick={() => window.open(OVERLAY_URL, "_blank", "noopener,noreferrer")}
            />
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
          <Metric label="HTTP" value={HTTP_BASE} />
          <Metric label="WebSocket" value={WS_URL} />
          <Metric label="Uptime" value="2h 14m" />
          <Metric label="Events" value="1,247" />
          <Metric label="MIDI ports" value="TRAKTOR X1 MK3, TRAKTOR Z1 MK2" span />
        </dl>
      </WobbleCard>

      {/* Switches */}
      <section className="mt-8 max-w-3xl">
        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Switches
        </h2>
        <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-bg-card">
          {SWITCH_DEFS.map(({ id, label, icon: Icon, description }) => (
            <div key={id} className="flex items-center justify-between gap-6 px-5 py-4">
              <div className="flex items-start gap-3">
                <Icon size={17} className="mt-0.5 shrink-0 text-text-dim" />
                <div>
                  <div className="text-sm font-medium text-text">{label}</div>
                  <div className="mt-0.5 max-w-md text-xs leading-relaxed text-text-dim">
                    {description}
                  </div>
                </div>
              </div>
              <Switch
                checked={switches[id]}
                label={label}
                onChange={(next) => setSwitches((prev) => ({ ...prev, [id]: next }))}
              />
            </div>
          ))}
        </div>
      </section>

      {/* Log panel */}
      <section className="mt-8 max-w-3xl">
        <h2 className="mb-3 flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          <Terminal size={14} className="text-accent" />
          Server Log
        </h2>
        <div className="mm-scroll h-56 overflow-y-auto rounded-xl border border-border bg-bg-primary p-4 font-mono text-xs leading-relaxed">
          {logs.map((entry, index) => (
            <div key={`${entry.ts}-${index}`} className="flex gap-3 whitespace-pre-wrap break-all">
              <span className="shrink-0 text-text-dim/70">{formatTimestamp(entry.ts)}</span>
              <span className={cn("shrink-0 uppercase", LEVEL_COLOR[entry.level])}>
                {entry.level.padEnd(5)}
              </span>
              <span className="text-text">{entry.line}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, span = false }: { label: string; value: string; span?: boolean }) {
  return (
    <div className={cn(span && "sm:col-span-2")}>
      <dt className="text-xs uppercase tracking-wider text-text-dim">{label}</dt>
      <dd className="mt-0.5 font-mono text-sm text-text">{value}</dd>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  tone = "neutral",
}: {
  icon: IconComponent;
  label: string;
  onClick: () => void;
  tone?: "neutral" | "accent";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        tone === "accent"
          ? "border-accent/40 bg-accent/15 text-accent hover:bg-accent/25"
          : "border-border bg-bg-elevated text-text hover:border-accent/40 hover:text-accent",
      )}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}
