/* HUD fade timeline — pure function, unit-tested by scripts/test_hud_alpha.js.
 *
 * RULE: fadeIn ramps off the card's APPEARANCE time (first event of an interaction),
 * never off the last event. Keying it off `last` made the card re-fade on every
 * value update (50 ms demo ticks / knob turns) -> visible blinking at bottom center.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MidiHudAlpha = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var FADE_IN_MS = 140;
  var FADE_OUT_MS = 400;

  /**
   * @param {number} now      current time (ms, single clock source)
   * @param {number} last     time of last event of this interaction
   * @param {number} appearAt time of FIRST event of this interaction
   * @param {number} ttl      card lifetime after last event (ms)
   * @returns {number} alpha 0..1
   */
  function hudAlpha(now, last, appearAt, ttl) {
    if (now - last > ttl) return 0; // expired
    var fadeIn = Math.min(1, Math.max(0, (now - appearAt) / FADE_IN_MS));
    var sinceLast = now - last;
    var fadeOut =
      sinceLast > ttl - FADE_OUT_MS
        ? Math.min(1, Math.max(0, (ttl - sinceLast) / FADE_OUT_MS))
        : 1;
    return Math.min(fadeIn, fadeOut);
  }

  return { hudAlpha: hudAlpha, FADE_IN_MS: FADE_IN_MS, FADE_OUT_MS: FADE_OUT_MS };
});