# Sidee — target true VIDAA app runtime, not Browser shortcut

Date: 2026-09-29

User requirement clarified:
- a Home/browser shortcut is NOT acceptable if it retains the VIDAA browser pointer;
- Nuvio must be launched in the TV's app runtime / launcher context, chromeless and remote-first.

Research result:
- VIDAA officially supports hosted web apps: the app is still a remote URL, but the Launcher/App Store starts it as an application context.
- Historical Hisense launcher source shows a distinct internal page/runtime named `app_lau_browser`.
- When the launcher handles a URL with browser-app command type, it calls `asyncStartApp("app_lau_browser", command, ...)`.
- `asyncStartApp` treats that page as module `app`, sets window size to 1920x1080, pauses TV/HbbTV state, opens the app page, closes the launcher and uses app-specific key handling.
- This is materially different from `app_hi_browser`, the normal browser.
- Therefore hiding the cursor with CSS or pinning a browser shortcut is not the final solution.

Current blockers already known:
- direct AppInfo.json registration is permission-gated on this VIDAA U9 firmware;
- Hisense_installApp/installApplication reaches AppConfig 503;
- official Store APIs use signed/authenticated requests.

New remaining technical route:
Find whether VIDAA U9 still exposes a bridge from the normal browser to the launcher/app-runtime start path, potentially through `omi_platform`, `opera_omi`, or a Hisense start/launch browser API. If yes, a public hosted launcher page could immediately hand off the Nuvio URL into the real app context without requiring a permanent PC.

Implemented on Sidee main:
- `315d35e9a0e41da067a77957febceb0e194604ee`: read-only launcher bridge probe in web/app.js.
- `e4e0850b10bde656772b8b40a2fbc1f3b16c0a06`: UI card/button "Inspect launcher bridge".

The probe:
- enumerates methods/properties on `omi_platform` and `opera_omi`;
- searches window globals for Hisense/start/launch/open/app/browser candidates;
- invokes NOTHING;
- saves results into `launcherBridgeProbe` in the normal session report.

## Next test

1. `git pull`
2. restart Sidee
3. open Sidee in the TV browser in the same context where Hisense APIs are available
4. press **Inspect launcher bridge**
5. reply `fatto bridge`

Then inspect `reports/latest.json` -> `launcherBridgeProbe`.

Decision:
- if a start/launch/browser/app bridge exists: implement a bounded Nuvio app-runtime launch experiment;
- if only `sendPlatformMessage` exists: research the specific non-destructive launcher message schema before sending anything;
- if no bridge exists: the only true app-context routes left are successful launcher registration (currently permission-gated) or official VIDAA partner/store distribution.
