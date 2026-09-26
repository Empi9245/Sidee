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
- controlled **Identity Override Lab**: discovers concrete identifiers already exposed by the TV/runtime and tests at most 8 of them against the same harmless read-only Appinfo request with guaranteed restoration
- one explicit **Run Install Diagnostic** workflow: before snapshot → Legacy diagnostic → verification → V2 diagnostic → verification → final summary
- Legacy-only and V2-only controls kept under **Advanced diagnostics**, not presented as competing solutions
- internal `HiUtils_createRequest` tracing during native install calls (including `installApplication` results)
- launcher refresh through `omi_platform` / `opera_omi`
- post-install verification using `Hisense_getInstalledApps`
- optional **read-only** `websdk/Appinfo.json` verification when HiUtils is available
- one continuously updated JSON report per diagnostic session under `reports/`
- editable generic target-app profile from the TV UI; the current default ID/name are `nuviodebug` / `Nuvio TV`

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
2. Set the TV DNS manually to the PC IP printed by Sidee.
3. Open the TV browser and visit `https://vidaahub.com`.
4. Run **Device / Environment Scan**.
5. Run **Permission & AppConfig Probe**.
6. Run **Runtime Identity Probe**.
7. If Sidee proves a normal runtime read path, **Read Client Information** becomes available for one manual read. If the inspected `vowOSContext.init()` source passes the strict zero-argument safety gate, **Initialize Runtime Context** also appears as a one-shot manual action.
8. Configure the target app if necessary.
9. Press **Run Install Diagnostic** only if Runtime Identity found a non-empty app identity. Sidee blocks repeated Legacy/V2 attempts while identity remains empty.
10. Read the always-visible Summary. A JavaScript callback of `0` is never treated as installation success.
11. Press **Export Report**.
12. Use the single `sidee-session-....json` file in `reports/`.

After testing, restore the TV DNS to Automatic.

> The trusted hostname used by the projects we inspected is **vidaahub.com**, not vidaa.com.


## Runtime identity probe

Sidee now has a dedicated **Runtime Identity Probe** for the VIDAA 9 permission investigation.

It records, without setters or security calls:

- the descriptor/owner/value path for `navigator.appIdentifier`;
- related Navigator properties containing app / identifier / client / context / VIDA / vow names;
- `vowOS.service.getIdentifier` source and its relationship to `navigator.appIdentifier`;
- the `vowOSContext` structure, prototype and function sources, including `getAppIdentifier`, `getAppId` and `init`;
- the existing Role ID / Customer ID read-only snapshots.

`vowOSContext.init()` is never automatic. Its manual **Initialize Runtime Context** action is hidden unless the actual runtime source is complete, non-native, explicitly zero-argument, identity-related, and free of HiUtils/native install, write, security, reset, network, navigation, or storage-write references. If the gate passes, Sidee captures BEFORE/AFTER identity and calls `init()` exactly once; it still does not retry installation automatically.

`window.clientInformation` stays inspect-only by default. Because the Hisense runtime exposes a vendor accessor, Sidee does not rely on generic browser semantics alone: the manual **Read Client Information** action appears only for a normal data property or when inspected `vowOSContext` source demonstrates a normal read path. The getter can then be read exactly once; the setter is never called.

To avoid repeating the already-proven anonymous-client 503 path, Legacy/V2 install diagnostics are blocked until the Runtime Identity Probe finds at least one non-empty app identity field.

The report also includes a compact runtime identity assessment: `IDENTITY PRESENT`, `ANONYMOUS-LIKE`, or `INCOMPLETE`. It explicitly keeps the unresolved lifecycle questions as **NOT PROVEN** rather than guessing that the launcher, browser, origin, or AppConfig is responsible. A manual `clientInformation` read is retained across later probe runs instead of being overwritten by a fresh inspect-only snapshot.

## Identity Override Lab

The **Identity Override Lab** is a controlled, reversible experiment for the VIDAA 9 AppConfig investigation.

It does not invent or brute-force identifiers. Candidate values are taken only from concrete data already exposed by the TV/runtime: current identity fields, app IDs present in the read-only `websdk/Appinfo.json`, IDs returned by `Hisense_getInstalledApps`, and narrowly matched scalar runtime data descriptors. Candidate strings are deduplicated, ranked by provenance, and only the first 8 are tested.

The lab first performs a baseline `HiUtils_createRequest("fileRead", {path:"websdk/Appinfo.json", mode:6})`. For each candidate it temporarily replaces only `vowOS.service.getIdentifier()`, repeats that same read-only request, records `ret/code/msg` plus the response, compares it with baseline, and restores the original function in `finally`. Responses identical to baseline reference the baseline copy instead of duplicating a large Appinfo payload.

Automatic conclusions are deliberately conservative:

- `NO_REAL_IDENTIFIER_AVAILABLE` when no concrete non-empty candidate exists;
- `IDENTIFIER_AFFECTS_BACKEND` only when the harmless local-service response actually changes;
- `INCONCLUSIVE` when the read-only response is equivalent, because `fileRead` is not known to share the `installApplication` permission gate;
- `IDENTIFIER_STRING_NOT_SUFFICIENT` is only used after the separate explicit candidate permission-gate test still receives the AppConfig permission rejection.

The separate **Candidate Permission Gate Test** lives under Advanced diagnostics. It is never part of the read-only lab or remote workflow. It may issue a real install request and therefore may install/register the target if the candidate is accepted.

## Target app profile

`config.json` keeps the target generic. The current defaults are app ID `nuviodebug` and name `Nuvio TV`; deployment URL and icon URL remain configurable from the Sidee UI and are not hardcoded to a LAN address.

The main install classifications are `AVAILABLE`, `REQUESTED`, `REJECTED`, `VERIFIED INSTALLED`, `NOT INSTALLED`, and `UNKNOWN`. If the internal HiUtils trace returns `ret:false`, code `503`, and the AppConfig permission-check message, Sidee classifies the request as `REJECTED` even if the outer callback is `0`.

## Reports

Sidee now uses one report per browser diagnostic session. The session ID is retained in `sessionStorage`, so navigation/reload within the same browser session keeps targeting the same server-side report filename.

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
  "runtimeIdentityProbe": {},
  "runtimeContextInitialization": {},
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


## Automatic GitHub report sync

Sidee can mirror diagnostic reports to GitHub automatically, without exposing any GitHub credential to the TV/browser JavaScript.

The default configuration is:

```json
"github_report_sync": {
  "enabled": true,
  "remote": "origin",
  "branch": "sidee-reports",
  "base_branch": "main",
  "latest_path": "reports/latest.json",
  "history_dir": "reports/sessions",
  "debounce_seconds": 2
}
```

After every local session save, the Python host queues the newest report. A short debounce coalesces rapid successive autosaves. The sync worker then uses the existing local Git checkout and its configured Git credentials to update a dedicated `sidee-reports` branch:

- `reports/latest.json` always contains the newest synced state;
- `reports/sessions/sidee-session-....json` preserves the session history.

The worker operates from a temporary detached Git worktree, so it does not switch branches, stage unrelated files, or commit the user's current working-tree changes. It never stores a GitHub token in `web/app.js`, the TV, or `config.json`. `GIT_TERMINAL_PROMPT=0` prevents Sidee from hanging on an interactive credential prompt.

Requirements for remote sync:
- Sidee must be running from a real Git checkout of this repository;
- the configured remote (default `origin`) must permit push using credentials already available to Git on the PC;
- Git must be installed.

If any Git operation fails, the local `reports/sidee-session-....json` remains authoritative and the TV UI reports the sync error. Diagnostic execution is never failed merely because GitHub is unavailable.

The current sync state is available locally at:

```
GET /api/reports/sync
```

Once a report has synced, another ChatGPT conversation with access to the GitHub repository can read `reports/latest.json` from branch `sidee-reports` directly; there is no need to download and attach the JSON manually.


## Session-armed remote read-only diagnostics

Sidee supports a deliberately narrow way to request a diagnostic from another ChatGPT conversation while the Sidee page is already open on the TV.

This is not a general remote-control channel. The TV page starts **disarmed** on every load. The user must press:

`Enable remote diagnostics for this page`

Once armed, and only while that page remains open, Sidee may accept one fixed read-only workflow requested through Git:

`baseline → Identity Override Lab → Permission Source Trace → Installed App Metadata → verification → report export/sync`

The request channel defaults to branch `sidee-control`, file `control/request.json`. The Python host polls that file and the TV polls only the local Sidee server.

The remote path cannot select arbitrary functions and cannot perform install/uninstall, Role/Customer setters, file writes, resets, arbitrary JavaScript or guessed HiUtils calls.

Each real request must carry a fresh `sidee-request-YYYYMMDD-HHMMSS-xxxx` ID and a future `expiresAt`. The page records the request ID and completion state in the normal diagnostic report. Therefore a ChatGPT turn can verify that its exact request completed by reading `remoteDiagnostic.lastRequestId` in `sidee-reports/reports/latest.json`.
