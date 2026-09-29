# Sidee — back to Store download/install path

Date: 2026-09-29

User explicitly wants the **real VIDAA Store download/install route**, not runtime-container or handoff workarounds.

## Important model correction

VIDAA officially supports hosted web apps. A hosted app is launched from a URL and downloads its resources from the remote server at runtime. Therefore an App Store "install" does not necessarily mean a binary app package is downloaded to the TV; for hosted apps it may primarily create/store launcher metadata, app identity, icon, URL and related Store state.

This is especially relevant to Duplecast because the installed app later talks to:
- `vidaa.duplecast.com`
- `files.duplecast.com`

So the next capture must determine empirically whether the Duplecast Store install does one of these:
1. downloads a real package/bundle from a download/CDN host; or
2. performs signed Store/launcher registration of a hosted URL plus metadata/assets.

Do not assume a package exists until traffic proves it.

## Previous useful capture

Session `sidee-20260929-173911-7b2f` successfully captured Store TLS flows through pktmon:
- 384 packet records
- 89,666 bytes
- 382 HTTPS packet records
- topology: `FILTERED_FLOW_VISIBLE_AFTER_NAT`
- SNI included:
  - `appstore-vidaa.vidaahub.com`
  - `tvmodules-vidaa.vidaahub.com`
  - `home-ui-eu.vidaahub.com`
  - `search-ui-eu.vidaahub.com`
  - `static-ui.vidaahub.com`
  - monitoring/journal hosts

That capture did **not** include the actual Duplecast install window, so no conclusion about package delivery was possible.

## New implementation

Commits:
- `10ae20912f6cbefc6116526ce1c8dcb20710ae29`
  - adds `store_download_capture` config
  - enabled by default
  - auto-arm on Sidee startup
  - target documented as Duplecast appId 1876
  - automatic capture window: 180 seconds
- `c895f314205e3d8752af47333646bafb8dfec3f6`
  - Sidee automatically arms pktmon after startup
  - first VIDAA Store DNS activity from the TV starts the TV-IP-filtered full capture
  - no dashboard click is required
  - capture automatically stops after 180 seconds and converts to PCAPNG/TXT
  - report sync happens through the existing `fullNetworkCapture` path
  - startup instructions now focus on normal Store install, not app-context tests

## Next test

1. `git pull --ff-only origin main`
2. fully restart Sidee as Administrator
3. TV DNS remains pointed to the Sidee PC
4. ensure Duplecast is uninstalled
5. open the **normal VIDAA App Store from the launcher**
6. search/open Duplecast and install it normally
7. do not use the Sidee dashboard
8. leave Store open until the capture has had enough time to include the install flow
9. reply `fatto download`

Then inspect the newest report/capture for:
- SNI appearing only during install
- `file-dl.vidaahub.com`
- `files.duplecast.com`
- new CDN/object-storage hosts
- a high-byte TLS flow coincident with Install
- absence of large package flow, which would support hosted-app metadata registration instead

If a package/download host is proven, continue tracing its supported Store flow.
If no package flow exists and the install is metadata/URL registration, refocus on the exact official launcher-registration request rather than looking for a nonexistent package.
