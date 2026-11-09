import { Coffee, Info, Link as LinkIcon, Plug, TriangleAlert, User } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { EvervaultCard, GlowingCard } from "../components/ui";
import { COFFEE_URL, REPO_URL } from "../lib/constants";

interface SwitchNote {
  title: string;
  body: string;
}

const SWITCH_NOTES: SwitchNote[] = [
  {
    title: "Demo Mode",
    body: "Feeds synthetic MIDI events so you can test the overlay and layout without a controller connected.",
  },
  {
    title: "NHL Native Mode",
    body: "Reads NI controllers' vendor HID reports directly, skipping loopMIDI. Experimental — see limitations.",
  },
  {
    title: "Auto-start",
    body: "Launches the sidecar server as soon as the app opens, so OBS picks up the overlay immediately.",
  },
];

const LIMITATIONS: string[] = [
  "Windows only — the shell is a WinUI 3 / WebView2 app.",
  "NHL native mode is partially decoded: the Z1 MK2 works, the X1 MK3 does not yet.",
  "Traktor MIDI CC range is 0–127; keys outside its catalog are silently dropped.",
  "Traktor must be closed while MidiMAT writes the TSI mapping.",
  "OBS browser source must be added manually (we provide the URL, not the source).",
];

export function Help() {
  return (
    <div className="mm-scroll h-full overflow-y-auto px-8 py-7">
      <header className="mb-6">
        <h1 className="text-[13px] font-semibold uppercase tracking-[0.18em] text-text-dim">
          Help
        </h1>
      </header>

      <div className="flex max-w-3xl flex-col gap-5">
        {/* What it is */}
        <Section icon={Info} title="What MidiMAT is">
          <p className="text-[13px] leading-relaxed text-text-dim">
            MidiMAT watches your Traktor controller and lights up a matching overlay in OBS the
            moment a knob, fader or button moves. It bundles the MIDI tap, the WebSocket
            broadcaster and the overlay editor behind one desktop app &mdash; no scripts, no
            terminal.
          </p>
        </Section>

        {/* Switches explained */}
        <Section icon={Plug} title="Switches explained">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {SWITCH_NOTES.map((note) => (
              <div key={note.title} className="rounded-lg border border-border bg-bg-elevated/40 p-3">
                <div className="text-[13px] font-medium text-text">{note.title}</div>
                <p className="mt-1 text-xs leading-relaxed text-text-dim">{note.body}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* Limitations */}
        <Section icon={TriangleAlert} title="Limitations">
          <ul className="flex flex-col gap-2">
            {LIMITATIONS.map((item) => (
              <li key={item} className="flex gap-3 text-[13px] leading-relaxed text-text-dim">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-warn" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </Section>

        {/* Sources */}
        <Section icon={LinkIcon} title="Sources">
          <p className="text-[13px] leading-relaxed text-text-dim">
            MidiMAT is open source. Builds, issues and the full architecture notes live in the
            repository.
          </p>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-3 inline-flex font-mono text-xs text-accent underline-offset-4 hover:underline"
          >
            {REPO_URL}
          </a>
        </Section>

        {/* Author + donate */}
        <EvervaultCard className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-elevated">
                <User size={18} className="text-text-dim" />
              </div>
              <div>
                <div className="text-sm font-medium text-text">Built by jardaKarlik</div>
                <p className="text-xs text-text-dim">
                  MidiMAT is a spare-time project. If it saves you a gig, consider buying a coffee.
                </p>
              </div>
            </div>
            <a
              href={COFFEE_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 rounded-md bg-warn/15 px-4 py-2 text-sm font-medium text-warn transition-colors hover:bg-warn/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warn/50"
            >
              <Coffee size={15} />
              Buy me a coffee
            </a>
          </div>
        </EvervaultCard>
      </div>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: ComponentType<{ size?: number | string; className?: string }>;
  title: string;
  children: ReactNode;
}) {
  return (
    <GlowingCard className="p-5">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text">
        <Icon size={16} className="text-accent" />
        {title}
      </h2>
      {children}
    </GlowingCard>
  );
}
