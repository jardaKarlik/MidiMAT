import { useCallback, useState } from "react";

import { ServerLog, type LogLine } from "@/components/midimat/server-log";
import { ServerStatusCard } from "@/components/midimat/server-status-card";
import { SwitchRow } from "@/components/midimat/switch-row";
import { HTTP_BASE, OVERLAY_URL, WS_URL } from "@/lib/constants";
import {
  ClientMessage,
  HostMessage,
  postToHost,
  useHostMessages,
  type LogLevel,
  type ServerLogPayload,
} from "@/lib/ipc";

// The design's seed log, kept verbatim so the Status screen matches it.
const initialLog: LogLine[] = [
  { time: "14:32:01", level: "INFO", message: "overlay: http://127.0.0.1:8080/overlay/index.html" },
  { time: "14:32:05", level: "INFO", message: "midi connected: TRAKTOR X1 MK3" },
  { time: "14:32:07", level: "INFO", message: "client connected: 127.0.0.1" },
  { time: "14:32:14", level: "INFO", message: "received MIDI: 90 40 7F (ch 1, note 64, vel 127)" },
  { time: "14:32:18", level: "INFO", message: "client disconnected: 127.0.0.1" },
];

const MAX_LOGS = 200;

const LEVEL_MAP: Record<LogLevel, LogLine["level"]> = {
  info: "INFO",
  debug: "INFO",
  warn: "WARN",
  error: "ERROR",
};

function toLogLine(payload: ServerLogPayload): LogLine {
  const parsed = new Date(payload.ts);
  const time = Number.isNaN(parsed.getTime())
    ? payload.ts
    : parsed.toLocaleTimeString([], { hour12: false });
  return { time, level: LEVEL_MAP[payload.level], message: payload.line };
}

export function Status() {
  const [demoMode, setDemoMode] = useState(false);
  const [nhlNative, setNhlNative] = useState(true);
  const [autoStart, setAutoStart] = useState(true);
  const [log, setLog] = useState<LogLine[]>(initialLog);

  useHostMessages(
    useCallback((message) => {
      if (message.type === ClientMessage.ServerLog) {
        setLog((prev) => {
          const next = [...prev, toLogLine(message.payload)];
          return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
        });
      }
    }, []),
  );

  return (
    <>
      <ServerStatusCard
        httpUrl={HTTP_BASE}
        wsUrl={WS_URL}
        uptime="2h 14m 36s"
        eventCount={12482}
        onRestart={() => postToHost(HostMessage.ServerRestart, {})}
        onStop={() => postToHost(HostMessage.ServerStop, {})}
        onOpenOverlay={() => window.open(OVERLAY_URL, "_blank", "noopener,noreferrer")}
      />

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Switches</h2>
        <div className="divide-y rounded-lg border bg-card shadow-card">
          <SwitchRow
            label="Demo Mode"
            description="Generate fake MIDI events for testing"
            checked={demoMode}
            onCheckedChange={setDemoMode}
          />
          <SwitchRow
            label="NHL Native Mode"
            description="Read HID directly from NI controllers"
            checked={nhlNative}
            onCheckedChange={setNhlNative}
          />
          <SwitchRow
            label="Auto-start"
            description="Launch the server when MidiMAT starts"
            checked={autoStart}
            onCheckedChange={setAutoStart}
          />
        </div>
      </section>

      <div className="mt-10">
        <ServerLog lines={log} onClear={() => setLog([])} />
      </div>
    </>
  );
}
