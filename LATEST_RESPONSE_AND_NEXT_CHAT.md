# Sidee — automatic installed-app runtime handoff test

Date: 2026-09-29

## Why dashboard D-pad work is stopped

Latest raw-IP session:
- client/server build match: `app-5dbeec3fbd21`
- `remoteInputProbe.events = []`
- `hiWebOsFrameAvailable = false`
- `keyboardAvailable = false`
- `Hisense_installApp = false`
- `Hisense_installApp_V2 = false`
- context remains `RAW_IP_BROWSER_CONTEXT`

Therefore the raw dashboard cannot claim D-pad/OK ownership with the browser-exposed surfaces currently available. More DOM key mapping changes are not useful.

## New test: real installed-app runtime -> cross-origin handoff

Implemented in:
- `b8b8dfb489ebfd38b83631bb5f2371507d14593e`

Flow:
1. Launch a real installed app context intercepted by Sidee (current config spoofs Smartone: `vidaa.smartone-iptv.com`).
2. Sidee bootstrap captures the real installed-app identity as before.
3. After the bootstrap report is successfully saved, the page automatically navigates to:
   `http://<PC-IP>:8080/app-runtime-handoff`
4. The handoff page automatically captures:
   - navigator.appIdentifier
   - vowOS serviceIdentifier
   - vowOSContext appIdentifier/appId
   - Hisense_SupportAppConfig
   - install API availability
   - omi_platform/opera_omi availability
   - raw remote key events
5. It updates the *same* app-context session report under:
   - `appRuntimeHandoffProbe.runtimePreserved`
   - `appRuntimeHandoffProbe.inputReachedPage`
   - `summary.appRuntimeHandoff`
   - `summary.handoffInput`

Classifications:
- `APP_RUNTIME_PRESERVED_AFTER_CROSS_ORIGIN_HANDOFF`
- `APP_RUNTIME_LOST_AFTER_CROSS_ORIGIN_HANDOFF`

## Next user test

1. `git pull --ff-only origin main`
2. fully restart Sidee as Administrator
3. keep the TV DNS pointed to the Sidee PC
4. launch **Smartone IPTV from the VIDAA launcher**, not the normal browser
5. do not touch the Sidee dashboard
6. Smartone should first show the Sidee app-context page briefly, then automatically switch to **Sidee · app runtime handoff**
7. once the handoff page is visible, press arrows + OK a few times
8. reply `fatto handoff`

Then inspect the newest `SMARTONE_APP_CONTEXT` session containing `appRuntimeHandoffProbe`.

Decision:
- if runtime is PRESERVED and input events are captured: hosted Nuvio can potentially be launched from an installed app shell while retaining real VIDAA app behavior; next step is handoff to Nuvio itself.
- if runtime is PRESERVED but input is not captured: app identity survives, but key routing is separately controlled; test same-origin shell/proxy.
- if runtime is LOST: cross-origin top-level navigation drops app identity; next step is a same-origin Nuvio shell/proxy under the installed app host.
