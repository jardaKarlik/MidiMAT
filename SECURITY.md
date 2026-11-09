# Security Policy

## Scope

MidiMAT is a **local desktop tool**. It does not have a server component, does not
collect telemetry, and does not send your data anywhere by default.

The security-relevant surface is deliberately small:

- The sidecar serves the overlay and editor over HTTP on `127.0.0.1` only
  (loopback, not reachable from your network).
- The WebSocket broadcaster also binds to `127.0.0.1`.
- The desktop app spawns a bundled sidecar process and reads/writes files under
  `%LOCALAPPDATA%\MidiMAT`.
- Setup may download and run the official loopMIDI installer **with your explicit
  click and a UAC prompt** — nothing is installed silently.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's [private vulnerability reporting](../../security/advisories/new) on this
repository, or email the maintainer at **j.karleek@gmail.com**. Include:

- what the issue is and its impact;
- steps to reproduce (a minimised proof-of-concept helps);
- the version/commit and your Windows version.

You can expect an acknowledgement within a few days. Please give us a reasonable
window to ship a fix before any public disclosure.

## Supported versions

MidiMAT is pre-1.0; only the latest `main` is supported with fixes. Once releases
begin, the table below will list supported versions.

| Version | Supported |
|---|---|
| `main` (unreleased) | ✅ |
| anything else | ❌ |

## Dependencies

Runtime dependencies are pinned in `requirements.txt`. If you believe a dependency has
a vulnerability that affects MidiMAT, a report is still welcome.
