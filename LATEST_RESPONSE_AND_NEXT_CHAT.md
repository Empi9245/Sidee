# Sidee — strategic pivot: install Nuvio as a VIDAA U9 Home Shortcut first

Date: 2026-09-29

## What changed

The packet-capture work proved the TV Store path is observable, but it also clarified that continuing to hunt for a "Duplecast package replacement" is not the best route to the actual goal.

Known facts on this TV:
- VIDAA U09.60 / MTK9603;
- Hisense_installApp / installApplication reaches the AppConfig permission gate and returns 503;
- direct websdk/Appinfo.json writes are permission-gated;
- official Store traffic is signed/authenticated and HTTPS;
- pktmon can see the real Store HTTPS flow through Windows ICS/NAT;
- older/custom VIDAA installers register HTML5 apps primarily as launcher entries pointing to a URL, not necessarily as a native binary package.

## Better route found

Hisense documentation for MT9603 + VIDAA U9 explicitly documents:
- Browser -> visit a webpage;
- use Add to Home;
- the webpage appears persistently in Home -> Shortcuts.

That gives a supported, persistent launcher entry with:
- no devkit;
- no permanent PC/server;
- no DNS override after setup;
- no AppConfig bypass;
- no Store signature bypass.

For Nuvio this is functionally close to the desired install because Nuvio is already a VIDAA-targeted HTML5 web app.

## Nuvio changes already made

Repo: Empi9245/nuviotvsmart main

- commit 218d4fd7b24bcdb395828c2f99ebb8ef503e6f3e
  - application-name, theme-color, favicon and touch icon metadata
- commit a5dc9c172f43df1c43e5f75238875dea77c41188
  - manifest id/scope and VIDAA-forced start_url:
    ./?platform=vidaa&source=home-shortcut
- commit af3b704c6a9dbacc56de4df559b1cf49a4af3365
  - service worker cache bump

Nuvio already had:
- VIDAA detection;
- 1920x1080 logical viewport;
- D-pad/remote support;
- VIDAA PWA manifest;
- service worker;
- fullscreen display request.

## Practical target

First goal: get Nuvio pinned to VIDAA Home Shortcuts from the TV Browser and verify that launching from Home:
1. opens the Nuvio TV build directly;
2. preserves VIDAA mode;
3. is usable without a PC or custom DNS;
4. survives TV restart;
5. has acceptable browser chrome/fullscreen behavior.

If that works, the user's practical installation goal is solved.

## True Store/My Apps route

A real Store app is a separate track. Public VIDAA documentation exposes a partner/developer portal and official App Store distribution is partner-controlled. Current firmware evidence does not support a safe unauthorised local replacement of signed Store metadata.

If a true Store listing is required, prepare Nuvio as the HTML5 VIDAA partner app and pursue VIDAA Partner onboarding rather than trying to bypass Store signatures.

## Next test

Use the deployed public Nuvio URL on the TV Browser with:
?platform=vidaa&source=home-shortcut

Then use VIDAA U9 Browser -> Add to Home.

After adding:
- return to Home;
- launch the Nuvio shortcut;
- restart TV and launch again;
- report whether browser chrome is visible, whether pointer appears, and whether D-pad/back/player behavior matches the existing VIDAA build.
