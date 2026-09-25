# Sidee

Sidee is a **standalone local VIDAA research + web-app installer toolkit**. It is not part of Nuvio TV Smart.

It combines the useful ideas found in:

- Stremio's `stremio-hisense-install`: serving an installer from the trusted `vidaahub.com` browser context, calling `Hisense_installApp`, and refreshing the launcher through the OMI bridge.
- `weinzii/vidaa-edge`: function discovery, VIDAA device diagnostics, `Hisense_getInstalledApps`, and read-only inspection through `HiUtils_createRequest`.

Sidee is deliberately more conservative on VIDAA 9: **direct writes to `websdk/Appinfo.json` are disabled**. First we scan what the firmware actually exposes.

## What it does

- local DNS server: redirects only `vidaahub.com` / `www.vidaahub.com` to your PC and forwards other DNS requests upstream
- local HTTPS server on port 443
- local dashboard/fallback on port 8080
- TV-friendly interface
- read-only scanner for Hisense / VIDAA / HiUtils / OMI APIs
- device/model/firmware diagnostics
- legacy `Hisense_installApp` install test
- separate `Hisense_installApp_V2` test when exposed by the firmware
- internal `HiUtils_createRequest` tracing during native install calls (including `installApplication` results)
- launcher refresh through `omi_platform` / `opera_omi`
- post-install verification using `Hisense_getInstalledApps`
- optional **read-only** `websdk/Appinfo.json` verification when HiUtils is available
- JSON reports saved automatically under `reports/`
- editable Nuvio target profile from the TV UI

## Important difference from older installers

A callback value of `0` from `Hisense_installApp` is **not displayed as a successful installation by itself**.

Sidee distinguishes:

1. install request accepted by the VIDAA API
2. internal HiUtils/installApplication result captured when interceptable
3. launcher refresh attempted
4. app actually found by a verification method

This is meant to investigate the VIDAA 9 situation where the browser says the operation succeeded but nothing appears on the TV.

## Quick start

### Windows

Double-click:

```
start-windows.bat
```

Approve the Administrator prompt. Python 3 and OpenSSL must be available in PATH.

### macOS / Linux

```bash
chmod +x start-mac-linux.sh
sudo ./start-mac-linux.sh
```

## TV steps

1. Start Sidee on a computer connected to the same LAN as the TV.
2. Sidee prints the PC's LAN IP.
3. On the Hisense TV, set the DNS server manually to that IP.
4. Open the TV browser.
5. Visit:
   ```
   https://vidaahub.com
   ```
6. Accept the local/self-signed certificate warning if VIDAA shows one.
7. **Run Read-only Scan first.**
8. Review the detected APIs.
9. Use Verify / Deep verification.
10. Only then try Install Nuvio.

After testing, restore the TV DNS to Automatic.

> The trusted hostname used by the projects we inspected is **vidaahub.com**, not vidaa.com.

## Nuvio target

`config.json` contains the Nuvio app ID/name profile. The deployment URL and icon are intentionally left blank until you enter the current Nuvio host. They can be entered directly from the Sidee TV interface and saved back to the host.

If your current Nuvio deployment uses a different URL, change it before pressing Install.

## Reports

Every scan/install attempt can be saved to:

```
reports/vidaa-YYYYMMDD-HHMMSS-xxxxxx.json
```

Those reports are the most useful next step for VIDAA 9 research: they show exactly which APIs your firmware exposes, the device information the browser reveals, the install callback, OMI refresh attempt, and whether Sidee could actually verify the app.

## Safety scope

Sidee is intended for TVs you own/control. The initial build performs no direct system-file writes. `HiUtils_createRequest` is used only for `fileRead` during explicit deep verification.
