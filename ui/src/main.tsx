import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Fonts are bundled locally (@fontsource) so the app works with zero network.
// We import the `latin` subset only — the default entry pulls every script
// (cyrillic/greek/vietnamese/…) and bloats the EXE with unused glyphs.
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-500.css";
import "@fontsource/jetbrains-mono/latin-700.css";

import "./styles/globals.css";

import { App } from "./App";

const container = document.getElementById("root");
if (!container) {
  throw new Error("MidiMAT UI: #root element not found in index.html");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
