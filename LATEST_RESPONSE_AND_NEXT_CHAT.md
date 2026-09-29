# Sidee — no-pointer diagnosis + app-context conclusion

Date: 2026-09-29

## Current raw-IP dashboard result

Latest browser-side session:
`sidee-20260929-185551-a556`

Runtime:
- URL: `http://192.168.1.5:8080/`
- access context: RAW_IP_BROWSER_CONTEXT
- browser: `odin`
- firmware: `V0000.09.60A.Q0707`
- OS: `U09.60`
- `Hisense_SupportAppConfig() = true`
- `serviceIdentifier = ""`
- `Hisense_installApp = unavailable`
- `Hisense_installApp_V2 = unavailable`
- `omi_platform = available`
- `opera_omi = available`
- both expose native:
  - `addPlatformEventListener`
  - `sendPlatformMessage`

Remote input telemetry:
- `remoteInputProbe.events = []`
- no keydown/keyup/keypress reached the page.

Interpretation:
- the briefly visible focus on the first Sidee button is programmatic `focus()`, not proof that the D-pad is reaching the DOM;
- when OK is pressed, VIDAA/browser consumes the key outside the page and DOM focus is lost;
- further keydown mapping fixes are not useful in this context.

## Does no-pointer / app context grant install permission?

No evidence for that, and prior real app-context captures directly argue against it.

Previously captured actual installed-app contexts:

Duplecast:
- accessMode `DUPLECAST_APP_CONTEXT`
- appId `1876`
- navigator app identifier contains appid 1876
- non-empty service/app identifier
- `Hisense_SupportAppConfig() = true`
- `installLegacy = false`
- `installV2 = false`
- later permission/write result: rejected / WRITE_DENIED

Smartone:
- accessMode `SMARTONE_APP_CONTEXT`
- appId `1470`
- navigator app identifier contains appid 1470
- non-empty service/app identifier
- `Hisense_SupportAppConfig() = true`
- `installLegacy = false`
- `installV2 = false`
- later permission/write result: rejected / WRITE_DENIED

Conclusion:
A real VIDAA hosted-app context changes identity and runtime behavior, but does NOT automatically expose the browser install APIs or AppInfo write permission. App runtime and app-install authorization are separate gates.

## Launcher bridge research

The current raw browser exposes `omi_platform.sendPlatformMessage`.

Public VIDAA installer examples use:
- type: `APPMessage`
- MsgType: `appControl`
- action: `updateAppState`
- source: `browser`
- startAppType: `0x2`
- event: `AllAppsUpdate`

That known message only asks the launcher to refresh its application list after an install. No verified public `start arbitrary URL as app` APPMessage action has been found yet. Do not invent launcher messages.

## Better next route

Instead of trying to make the raw-IP dashboard respond to D-pad, test **app-context handoff**:

1. enter Sidee through a real installed app container (Duplecast or Smartone), where VIDAA already assigns app identity;
2. from that container, navigate/handoff to a controlled Nuvio-compatible page;
3. automatically measure after the navigation:
   - whether navigator.appIdentifier/appId stays 1876/1470;
   - whether serviceIdentifier remains non-empty;
   - whether D-pad events reach the page;
   - whether browser chrome/pointer stays absent;
4. if cross-origin navigation preserves app runtime, Nuvio can remain publicly hosted and use an installed app as the runtime shell;
5. if cross-origin loses the app context, test same-origin proxy/service-worker shell next.

This route targets the user's actual goal (Nuvio behaving as a VIDAA app) without relying on unavailable browser install APIs.
