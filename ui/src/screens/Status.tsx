import { ServerLog } from "@/components/midimat/server-log";
import { ServerStatusCard } from "@/components/midimat/server-status-card";
import { SwitchRow } from "@/components/midimat/switch-row";
import { HTTP_BASE, OVERLAY_URL, WS_URL } from "@/lib/constants";
import { HostMessage, postToHost } from "@/lib/ipc";
import { useStatus } from "@/lib/status-context";

export function Status() {
  // The log and config live in App (the shell streams `server:log` from startup,
  // so subscribing here would miss earlier lines). `config` defaults below match
  // ConfigStore's defaults until `config:loaded` arrives.
  const { log, clearLog, config, saveServerFlags } = useStatus();

  const server = config?.server;

  return (
    <>
      {/* Uptime / event count are pending a real source (the sidecar's /api/health). */}
      <ServerStatusCard
        httpUrl={HTTP_BASE}
        wsUrl={WS_URL}
        uptime={"\u2014"}
        eventCount={0}
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
            checked={server?.demo_mode ?? false}
            onCheckedChange={(checked) => saveServerFlags({ demoMode: checked })}
          />
          <SwitchRow
            label="NHL Native Mode"
            description="Read HID directly from NI controllers"
            checked={server?.nhl_mode ?? true}
            onCheckedChange={(checked) => saveServerFlags({ nhlMode: checked })}
          />
          <SwitchRow
            label="Auto-start"
            description="Launch the server when MidiMAT starts"
            checked={server?.auto_start ?? true}
            onCheckedChange={(checked) => saveServerFlags({ autoStart: checked })}
          />
        </div>
      </section>

      <div className="mt-10">
        <ServerLog lines={log} onClear={clearLog} />
      </div>
    </>
  );
}
