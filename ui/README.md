# MidiMAT — Management UI

The React + Tailwind management UI for MidiMAT. It is rendered inside the native
WinUI 3 shell's **WebView2** control, which maps the virtual host
**`https://midimat.local/`** onto `app/Resources/ui`.

## Stack

| Concern     | Choice                                                          |
| ----------- | --------------------------------------------------------------- |
| Framework   | React 19 + TypeScript                                           |
| Bundler     | Vite (relative `base: "./"` for the WebView2 virtual host)       |
| Styling     | Tailwind CSS 4 (`@tailwindcss/vite`, CSS-first `@theme` tokens)  |
| Animation   | Framer Motion (`prefers-reduced-motion` aware)                   |
| Icons       | lucide-react                                                     |
| Fonts       | `@fontsource/inter` + `@fontsource/jetbrains-mono` (bundled offline) |

## Commands

```powershell
npm install        # install dependencies
npm run dev        # local dev server at http://localhost:5173 (browser, no shell)
npm run build      # typecheck + build → ../app/Resources/ui
npm run preview    # serve the production bundle locally
npm run typecheck  # tsc --noEmit only
```

### Build output

`npm run build` writes the production bundle **directly into `app/Resources/ui`**
(configured via `build.outDir` with `emptyOutDir: true`). The shell's
`.csproj` picks it up with:

```xml
<Content Include="Resources\ui\**\*" CopyToOutputDirectory="PreserveNewest" />
```

A tiny Vite plugin re-creates `app/Resources/ui/.gitkeep` after each build, because
`emptyOutDir` wipes the folder first. The folder is otherwise gitignored so built
assets are never committed.

## How the shell hosts it

- The shell calls `WebView2.CoreWebView2.SetVirtualHostNameToFolderMapping("midimat.local", "Resources/ui", …)`
  and navigates to `https://midimat.local/index.html`.
- Because the host is virtual, **all asset URLs must be relative** — hence
  `base: "./"` in `vite.config.ts`. Absolute (`/…`) URLs would resolve against
  the virtual host root and 404.
- The UI talks to the shell over `window.chrome.webview` (see `src/lib/ipc.ts`).
  Outside the shell (plain browser / `npm run dev`) that object is absent and the
  bridge degrades to console logging instead of throwing, so the UI still runs.

## Layout

```
ui/
├── index.html               # entry document
├── vite.config.ts           # base "./", outDir ../app/Resources/ui, "@" → src alias
├── tsconfig.json            # "@/*" → "src/*"
├── public/
│   └── midimat-logo.svg     # approved knob-mark logo
└── src/
    ├── main.tsx             # React root + @fontsource imports
    ├── App.tsx              # nav state + host messages + page transitions
    ├── components/
    │   ├── layout/          # PageTransition
    │   ├── midimat/         # app-shell, app-sidebar, midimat-logo, server-log,
    │   │                    #   server-status-card, setup-card, status-dot, switch-row
    │   ├── setup/           # SetupWizard + the 6 step components + metadata
    │   └── ui/              # shadcn-style button.tsx, switch.tsx (Radix)
    ├── hooks/               # usePrefersReducedMotion
    ├── lib/                 # ipc.ts (typed bridge), constants.ts, navigation.tsx,
    │                        #   status-context.tsx, utils.ts
    ├── screens/             # SetupSummary, Status, Editor, MapDevice, Help (see index.ts)
    └── styles/globals.css   # Tailwind 4 @theme design tokens
```

**Screens:** all five — Setup Summary, Status, Editor, Map New Device (device mapper) and Help
— plus the first-run **setup wizard** (`components/setup/SetupWizard.tsx`, a full-screen
overlay that runs over the shell). Imports use the `@` → `src` alias (set in both
`vite.config.ts` and `tsconfig.json`). Fonts ship **offline** via `@fontsource` (imported in
`main.tsx`) — no CDN and no `public/fonts/` directory.

## IPC

`src/lib/ipc.ts` mirrors `app/Services/IpcBridge.cs` (`IpcMessageTypes`) exactly.
Keep the string literals in sync: `navigate`, `setup:start`, `setup:complete`,
`server:restart`, `server:stop`, `config:save` (React → C#) and `deps:status`,
`server:log`, `setup:progress`, `config:loaded` (C# → React).
