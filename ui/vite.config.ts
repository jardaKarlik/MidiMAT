import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const here = dirname(fileURLToPath(import.meta.url));

// The WinUI 3 shell maps the virtual host https://midimat.local/ onto
// app/Resources/ui. Vite therefore MUST emit relative URLs (base: "./") and
// write straight into the folder the .csproj globs as <Content Include="Resources\ui\**\*">.
const outDir = resolve(here, "../app/Resources/ui");

/**
 * `build.emptyOutDir` wipes app/Resources/ui on every build (so stale hashed
 * assets never linger). That also removes the tracked `.gitkeep` that keeps the
 * folder present in a fresh clone, so re-create it once the bundle is written.
 * The file is gitignored-exempt via the root .gitignore (`!app/Resources/ui/.gitkeep`)
 * and is harmless to the C# Content glob.
 */
function preserveGitkeep(): Plugin {
  return {
    name: "midimat-preserve-gitkeep",
    closeBundle() {
      writeFileSync(resolve(outDir, ".gitkeep"), "");
    },
  };
}

export default defineConfig({
  // Relative asset URLs — required for the WebView2 virtual host mapping.
  base: "./",
  // `@/` points at src/ so the ported design components keep their original
  // import specifiers verbatim (matches the design's tsconfig alias).
  resolve: {
    alias: { "@": resolve(here, "src") },
  },
  plugins: [react(), tailwindcss(), preserveGitkeep()],
  build: {
    outDir,
    emptyOutDir: true,
    target: "es2022",
    // Offline app: never reference a remote sourcemap host.
    sourcemap: false,
    // WebView2 is evergreen Chromium; no need for legacy transforms.
    assetsInlineLimit: 4096,
  },
  server: {
    // Dev-only convenience; the shell points at https://midimat.local/ in prod.
    port: 5173,
    strictPort: false,
  },
});
