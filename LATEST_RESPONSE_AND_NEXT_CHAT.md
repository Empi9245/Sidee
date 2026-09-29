# Sidee — dashboard input failure + no-pointer permission test

Date: 2026-09-29

Observed after user's latest TV test:
- browser chrome can still be controlled;
- Sidee dashboard itself cannot be controlled;
- pointer is absent;
- no `runtimeSurfaceAutoProbe`, `remoteInputProbe` or `launcherBridgeProbe` appeared in the synced session reports.

Latest synced session at ~19:05 local:
- `sidee-20260929-190401-363a`
- only Store DNS discovery data was present;
- there was no browser-side auto telemetry.

Important interpretation:
- pointer absence alone does NOT prove Sidee is running as a registered VIDAA app;
- however, if the page context really changed, its native identifier/AppConfig authorization could differ, so a fresh install-gate test in that exact context is worth doing;
- the lack of browser-side report strongly suggests the dashboard JS is not reaching its startup section.

Likely failure mode found:
- VIDAA may be serving a stale `index.html` together with a newer `app.js`;
- the newer JS previously bound listeners with direct calls such as `$("launcherBridgeProbeBtn").addEventListener(...)`;
- if the cached HTML did not contain that newly-added element, JS execution stopped before startup, explaining:
  - no initial focus,
  - no input telemetry,
  - no runtime snapshot,
  - no automatic reports,
  - apparently dead dashboard controls.

Fixes on main:
- `43808eeb1d9bbbe575f16ffa939f41fe254eb95b`
  - all dashboard event binding now tolerates missing/stale HTML elements;
  - mixed cached HTML/JS can no longer abort the entire script.
- `150d6015940dea8b7e7334df13e5b273462163c7`
  - when the new client actually starts, Sidee automatically snapshots the current VIDAA runtime and runs one install-permission attempt for the configured Nuvio target;
  - no dashboard click is required;
  - result is saved as `automaticRuntimeInstallProbe`.
- prior commits:
  - `e8a15598...` automatic runtime + raw remote input telemetry
  - `49302086...` initial focus seeding

Current configured Nuvio target is still:
`http://192.168.1.5:4173/?wrapper=vidaa`

This is suitable only as a permission/runtime experiment; it is not the desired permanent PC-free final URL. The user's Vercel project was previously paused and no exact active public Vercel URL is currently available.

## Next action

Update the local Sidee checkout to current main and restart the process so the TV cannot keep executing the broken mixed dashboard:

`git pull --ff-only origin main`

Then fully stop the old Sidee process and start it again as Administrator.

On the TV:
- close the Sidee/browser page completely;
- reopen Sidee;
- no button interaction is required;
- leave the page open for several seconds.

Then reply `fatto auto`.

Inspect newest session files for:
- `runtimeSurfaceAutoProbe`
- `launcherBridgeProbe`
- `automaticRuntimeInstallProbe`
- `remoteInputProbe`

Decision:
- if automaticRuntimeInstallProbe is `INSTALLED/PASSED`, the no-pointer context has materially different install permission and we can proceed to register a permanent hosted Nuvio URL;
- if it still returns 503 AppConfig, no-pointer mode did not change install authorization;
- if no browser-side fields appear again, the TV is still not executing the new client and the next step is to move the auto-probe into an inline bootstrap served directly by index.html (before app.js), removing app.js startup as a dependency.
