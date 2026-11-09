import { Coffee, Info, Link, Plug, TriangleExclamationPoint, User } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { COFFEE_URL, REPO_URL } from "@/lib/constants";

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

function openCoffee(): void {
  window.open(COFFEE_URL, "_blank", "noopener,noreferrer");
}

export function Help() {
  return (
    <div className="flex flex-col gap-5">
      <Section icon={Info} title="What MidiMAT is">
        <p className="text-sm leading-relaxed text-muted-foreground">
          MidiMAT watches your Traktor controller and lights up a matching overlay in OBS the moment
          a knob, fader or button moves. It bundles the MIDI tap, the WebSocket broadcaster and the
          overlay editor behind one desktop app — no scripts, no terminal.
        </p>
      </Section>

      <Section icon={Plug} title="Switches explained">
        <div className="grid gap-3 sm:grid-cols-3">
          {SWITCH_NOTES.map((note) => (
            <div key={note.title} className="rounded-md border bg-inset p-4">
              <h3 className="text-sm font-semibold">{note.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{note.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={TriangleExclamationPoint} title="Limitations">
        <ul className="flex flex-col gap-3">
          {LIMITATIONS.map((item) => (
            <li key={item} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-warning" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <Section icon={Link} title="Sources">
        <p className="text-sm leading-relaxed text-muted-foreground">
          MidiMAT is open source. Builds, issues and the full architecture notes live in the
          repository.
        </p>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-3 inline-block font-mono text-sm text-primary underline-offset-4 hover:underline"
        >
          {REPO_URL}
        </a>
      </Section>

      <Section icon={User} title="Built by jardaKarlik">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <p className="max-w-lg text-sm leading-relaxed text-muted-foreground">
            MidiMAT is a spare-time project. If it saves you a gig, consider buying a coffee.
          </p>
          <Button variant="outline" onClick={openCoffee}>
            <Coffee /> Buy me a coffee
          </Button>
        </div>
      </Section>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-card p-6 shadow-card">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md border bg-raised">
          <Icon className="size-5 text-foreground" strokeWidth={1.75} />
        </span>
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}
