# Sidee — determine whether current no-pointer mode changed runtime permissions

Date: 2026-09-29

User observation:
- pointer is now absent inside the TV page;
- VIDAA browser chrome itself remains controllable;
- Sidee dashboard controls are still not selectable.

Do NOT infer from pointer absence alone that Sidee is running as a registered VIDAA app. Pointer mode and app runtime are separate questions.

Important possibility:
- if the page really moved from normal browser context into a hosted-app/launcher context, the native identity/identifier presented to VIDAA services could change;
- because the existing install failure is an AppConfig/permission check, a changed native identity would be worth testing;
- however the current report cannot establish this because latest.json is currently being overwritten by the Store DNS/install probe session.

Implemented on Sidee main:
- `e8a15598b00f2c7421bb7e4af2e2bfabff924b31`
  - automatic runtime surface snapshot on page load;
  - records Hisense current browser, firmware/OS, AppConfig support, install API availability, vowOS/vowOSContext, service identifier, clientInformation, omi_platform/opera_omi methods;
  - captures raw keydown/keyup/keypress events without requiring a click;
  - autosaves remote input telemetry after remote activity;
  - adds keyup fallback when VIDAA suppresses/changes keydown behavior.
- `1ab3c0271f97469b46667f75e1af6d44e5754431`
  - visible automatic remote telemetry state card.
- `49302086d9554f6dbd4b07887bd189df493c0553`
  - seeds initial DOM focus on the first visible dashboard control at load.

## Next test

1. `git pull`
2. restart Sidee
3. open Sidee on TV in the current no-pointer mode
4. do NOT click anything
5. press: Right, Down, OK, Left, Up, OK
6. wait a few seconds for autosave
7. reply `fatto input`

Then inspect the newest session report (not only reports/latest.json) for:
- runtimeSurfaceAutoProbe
- remoteInputProbe.events
- launcherBridgeProbe
- serviceIdentifier
- clientInformation
- currentBrowser
- install API availability

Decision:
- if runtime identity/identifier differs from prior vidaahub browser context, run ONE explicit install permission test in this exact context;
- if identity is unchanged, no-pointer mode did not grant install permission and the dashboard issue is purely input/focus;
- if no raw key events arrive at all, the browser/OS is consuming D-pad before the page and Sidee must use a native/launcher input bridge rather than DOM keyboard handlers.
