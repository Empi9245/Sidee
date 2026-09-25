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
- one continuously updated JSON report per diagnostic session under `reports/`
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

Sidee now uses one report per browser diagnostic session.

Session IDs use:

```
sidee-YYYYMMDD-HHMMSS-xxxx
```

and the server derives the only allowed report filename:

```
reports/sidee-session-YYYYMMDD-HHMMSS-xxxx.json
```

The same file is updated after the main phases (scan, Permission/AppConfig Probe, verification, and install diagnostic). Saving the target also syncs it into the same session report. **Export Report** only makes sure the newest in-memory state has been written; it does not create a second JSON.

The browser sends `sessionId` plus the report body to:

```
POST /api/reports/session
```

The backend accepts only `sessionId` values matching `^sidee-\d{8}-\d{6}-[a-f0-9]{4}$`, derives the filename server-side, checks the resolved report directory, and writes atomically with a temporary file plus `os.replace`. Arbitrary paths are never accepted. The old `POST /api/report` endpoint no longer writes timestamped legacy reports and returns HTTP 410.

The report is organized as:

```json
{
  "sessionId": "...",
  "startedAt": "...",
  "updatedAt": "...",
  "summary": {},
  "environment": {},
  "permissionProbe": {},
  "target": {},
  "installDiagnostic": {},
  "verification": {},
  "raw": {
    "snapshots": {}
  }
}
```

`summary` is progressively filled with firmware/model/OS/API/browser/origin availability flags, AppConfig status, install request/internal permission result, verification, and the final diagnostic conclusion.

Installed-app and `websdk/Appinfo.json` results inside `verification` are compact: count plus a short per-app identity record (`id`, `name`, URL/start command, store type, target match, and a small number of useful identity fields). Full runtime payloads are not copied into every verification/install attempt.

At most one safe-serialized raw copy is kept for each significant snapshot:

- `raw.snapshots.installedAppsBefore`
- `raw.snapshots.installedAppsAfter`
- `raw.snapshots.appInfoBefore`
- `raw.snapshots.appInfoAfter`

Serialization is defensive against circular references, functions, `undefined`, `Error` objects, accessors and problematic DOM/native objects, with hard size/depth/property limits derived from the Permission Probe limits.

`GET /api/reports/latest` and `GET /api/reports` remain available.

## Safety scope

Sidee is intended for TVs you own/control. The initial build performs no direct system-file writes. `HiUtils_createRequest` is used only for `fileRead` during explicit deep verification.
