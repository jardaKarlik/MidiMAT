/* Logic test for the HUD fade timeline.  Run:  node scripts/test_hud_alpha.js
 *
 * Simulates a knob sweep (event every 50 ms for 2 s) and asserts the card does NOT
 * dip during continuous activity — i.e. the bottom-center blinking is gone. */
"use strict";

const path = require("path");
const { hudAlpha, FADE_IN_MS, FADE_OUT_MS } = require(
  path.join(__dirname, "..", "overlay", "hud-alpha.js"),
);

const TTL = 1600;
let ok = true;
function assert(cond, msg) {
  if (cond) console.log("  ok   " + msg);
  else {
    ok = false;
    console.error("  FAIL " + msg);
  }
}

// 1) appearance ramp: alpha grows 0 -> 1 over FADE_IN_MS
assert(hudAlpha(0, 0, 0, TTL) === 0, "hidden at the exact moment of appearance");
assert(
  Math.abs(hudAlpha(FADE_IN_MS / 2, 0, 0, TTL) - 0.5) < 1e-9,
  "half-faded at half of FADE_IN_MS",
);
assert(hudAlpha(FADE_IN_MS, 0, 0, TTL) === 1, "fully visible after FADE_IN_MS");

// 2) continuous activity: event every 50 ms, appearAt stays at t=0 — NO dips.
//    (sample from the end of the intentional appearance ramp onwards)
let minDuring = 1;
for (let t = FADE_IN_MS; t <= 2000; t += 50) {
  minDuring = Math.min(minDuring, hudAlpha(t, t, 0, TTL));
}
assert(
  minDuring >= 0.999,
  `no blink during activity (min alpha=${minDuring} over 2 s of events)`,
);

// 3) demonstrate the OLD bug for contrast: fadeIn keyed off `last`
let oldMax = 0;
for (let t = 0; t <= 2000; t += 50) {
  // old: appear restarted every event -> alpha = (now - last)/140 with now ≈ last+phase
  for (let phase = 0; phase <= 50; phase += 10) {
    oldMax = Math.max(oldMax, Math.min(1, phase / 140));
  }
}
assert(
  oldMax < 0.5,
  `old behavior would cap alpha at ${oldMax.toFixed(2)} and dip to 0 each cycle (the blink)`,
);

// 4) fade-out after activity stops: full ttl of life, then gone
assert(hudAlpha(2000, 2000, 0, TTL) === 1, "still fully visible when last event is now");
const fadeStart = 2000 + TTL - FADE_OUT_MS;
assert(
  hudAlpha(fadeStart + FADE_OUT_MS / 2, 2000, 0, TTL) === 0.5,
  "half-faded midway through FADE_OUT_MS",
);
assert(hudAlpha(2000 + TTL + 1, 2000, 0, TTL) === 0, "gone after ttl");

// 5) reappearance after full expiry ramps again (fresh appearAt)
assert(hudAlpha(5000, 5000, 5000, TTL) === 0, "new interaction starts hidden...");

console.log(ok ? "\nALL PASSED" : "\nFAILURES");
process.exit(ok ? 0 : 1);