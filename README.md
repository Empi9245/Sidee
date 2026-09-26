# Sidee

## Current investigation — legacy writer context (2026-09-26)

The latest TV report (`sidee-20260926-172629-e5b8`, build match true) found
`Hisense` without `File` or `loadLibrary`, and no usable `HiBrowser` surface in
the vidaahub browser context. No legacy read/write occurred. Do not repeat the
HiUtils 503, identifier, origin or install tests described in the historical
sections below. Devkit is outside this investigation.

Use **Inspect HSPDK Context (read-only)** in **Legacy Hisense File Writer**.
The report's `legacyHspdkContext` records both named roots, descriptor/prototype
metadata, concrete global objects exposing `File`/`loadLibrary`, and bounded
function-source matches. It never calls a getter, loader or file operation.
`FILE_PAIR_OBSERVED_NOT_TESTED` means presence only, not permission.

After restarting Sidee, the existing Smartone/Duplecast bootstrap captures the
same HSPDK evidence automatically and queues it for report sync. Its previous
automatic HiUtils no-op write has been removed. Compare these reports with the
browser capture to determine whether the legacy surface changes by context.
No system page exposing HSPDK on the tested firmware has yet been identified.

Local checks: `node tests/hspdk-context.test.js` and
`python -B tests/test_hspdk_bootstrap.py` (requires Node.js).

Sidee is a **standalone local VIDAA research + web-app installer toolkit**. It is not part of Nuvio TV Smart.

It combines the useful ideas found in:

- Stremio's `stremio-hisense-install`: serving an installer from the trusted `vidaahub.com` browser context, calling `Hisense_installApp`, and refreshing the launcher through the OMI bridge.
- `weinzii/vidaa-edge`: function discovery, VIDAA device diagnostics, `Hisense_getInstalledApps`, and read-only inspection through `HiUtils_createRequest`.

Sidee is deliberately conservative on VIDAA 9. Direct `websdk/Appinfo.json` writes are available only through explicit, backup-protected flows: first an exact no-op write-back capability test, then separately triggered add/restore actions.


## VIDAA Store catalog transport trace — 2026-09-26

Sidee now has a pass-through-only observer for the real VIDAA Store catalog host:

`category-ui.vidaahub.com`

This was added after verifying the public `PhasedGapple/FuVIDAA-API` PoC, which proxies that host and handles `/api/v1.0.0/categoryApi/categoryFirstResult` with VIDAA catalog metadata including `appInfo.openMode`, `unifiedAppName`, `packaged` and related fields.

The Sidee implementation does **not** modify Store responses. When the TV DNS points to Sidee and the official VIDAA Store connects to that host, Sidee forwards the request to the real HTTPS upstream and records only bounded diagnostics:

- DNS hit;
- TLS SNI hit;
- HTTP method/path;
- query parameter names only;
- upstream status/content type/response length;
- bounded, non-sensitive catalog metadata from JSON responses.

Sidee does not persist request headers, request bodies, query values, cookies, authorization values, tokens, session identifiers, signature material or certificate-like values. Sensitive JSON keys are skipped. The returned upstream body is passed through unchanged.

Trace status is exposed at `GET /api/store-catalog-trace` and is also persisted in `storeCatalogTrace` reports with states such as `DNS_ONLY`, `TLS_SNI_ONLY`, `HTTP_PROXY_ACTIVE`, `REQUESTS_CAPTURED`, and `PROXY_ERROR`.

The generated multihost certificate now uses a new filename and includes `category-ui.vidaahub.com` in its SAN, so an older Sidee certificate without that hostname is not silently reused.

For the real-TV trace: start Sidee, point TV DNS to the Sidee PC, open the official VIDAA Store, browse a category, and open the detail page of an existing app. Do not press Install during this first transport-only phase.



### Passive Store domain discovery

If the fixed `category-ui.vidaahub.com` trace stays completely silent, Sidee now records a **passive DNS-only** discovery set while leaving those DNS answers untouched and forwarded normally.

The persisted scope is deliberately narrow:
- any `*.vidaahub.com` hostname;
- `api-launcher-*.hismarttv.com`;
- `auth-launcher-*.hismarttv.com`;
- `unified-ter-*.hismarttv.com`.

No generic browsing/DNS history is stored. The report section is `storeDomainDiscovery`; it keeps only hostname, DNS query type, count, and first/last timestamps. It does not spoof newly discovered hosts, intercept TLS, or store DNS payloads/query values.

This exists because the Q0707 test produced no DNS/SNI/HTTP hit for `category-ui.vidaahub.com`. Public evidence also shows other VIDAA Store-family hosts such as `appstore-vidaa.vidaahub.com` and `vidaa-base-auth-oc.vidaahub.com`, so the next step is to observe which hostname this TV actually asks for before intercepting anything else.

## What it does

- local DNS server: redirects only `vidaahub.com` / `www.vidaahub.com` to your PC and forwards other DNS requests upstream
- local HTTPS server on port 443
- local dashboard/fallback on port 8080
- raw-IP HTTP A/B test endpoint on port 8181, used only to compare VIDAA API/permission behavior without the `vidaahub.com` DNS/origin path
- TV-friendly interface
- read-only scanner for Hisense / VIDAA / HiUtils / OMI APIs
- device/model/firmware diagnostics
- backup-protected **Direct AppInfo Write Lab**: reads and immutably backs up the exact registry, writes the same content back through the documented `fileWrite` call, and verifies hash/structure on immediate readback
- controlled **Identity Override Lab** remains implemented but is temporarily paused while the direct AppInfo path is tested
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
   - For the explicit origin A/B comparison only, Sidee also prints `http://<PC-IP>:8080`. Open that URL without changing DNS, capture baseline, and run only the backup-protected **Test AppInfo Direct Write** no-op test.
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

## Direct AppInfo Write Lab

The current priority is the direct registry path reported for VIDAA 9. Sidee uses the documented shape:

```javascript
HiUtils_createRequest('fileWrite', {
  path: 'websdk/Appinfo.json',
  mode: 6,
  writedata: rawRegistry
});
```

The first **Test AppInfo Direct Write** action is a no-op capability test: it reads the current registry, validates JSON, stores the complete raw string and an immutable server-side backup, writes the exact same string, reads it again immediately, and compares hash, length, AppInfo count and structure.

Possible results are `WRITE_ALLOWED_AND_IDENTICAL`, `WRITE_DENIED`, `WRITE_CHANGED_CONTENT`, `READBACK_FAILED` and `INCONCLUSIVE`. Nuvio is never added by this first test.

Only after `WRITE_ALLOWED_AND_IDENTICAL` does **Add Nuvio to AppInfo** become enabled. The direct-entry shape follows fields shared by the Pikabu Jellyfin example and the vidaa-edge new method (`Type: Browser`, `StoreType: custom`). Observed fields such as `openMode`, `venderId` and `packaged` are intentionally omitted because the direct-write examples do not require them and the TV’s existing apps use varying values.

**Restore AppInfo Backup** can only use an immutable backup generated by Sidee for the same session. Restore first backs up the current registry again, validates session/backup/hash, writes the saved raw string, and confirms the readback.

The session-armed remote channel supports the no-op capability test as a fixed workflow, but it never remotely adds Nuvio or performs restore.

### Real TV result — 2026-09-26

On the tested Hisense `50E70LEVS_0003`, firmware `V0000.09.60A.Q0707`, the backup-protected no-op direct write was executed with `buildMatch:true`. The exact registry was backed up first, `fileWrite` returned `ret:false`, `code:503`, `client request permission check error, please check appconfig`, and the immediate readback remained byte/hash/structure identical with 3 AppInfo entries.

Therefore this firmware does **not** allow the direct Jellyfin-style AppInfo write from the current Sidee client context. Nuvio was not added. The active next research path is the Identity Override Lab.

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

Sidee is intended for TVs you own/control. Direct system-file writes are restricted to explicit AppInfo operations with a pre-write immutable backup and immediate readback verification. The first capability test writes the exact content it just read; app addition and restore remain separate explicit actions.


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

Once armed, and only while that page remains open, Sidee may accept one of two fixed workflows requested through Git:

- `baseline → Permission Source Trace → Installed App Metadata → verification → report export/sync`
- `Direct AppInfo no-op write → report export/sync` (exact read/backup/write-back/readback only)

The request channel defaults to branch `sidee-control`, file `control/request.json`. The Python host polls that file and the TV polls only the local Sidee server.

The remote path cannot select arbitrary functions and cannot add or restore AppInfo entries, perform install/uninstall, Role/Customer setters, resets, arbitrary JavaScript or guessed HiUtils calls.

Each real request must carry a fresh `sidee-request-YYYYMMDD-HHMMSS-xxxx` ID and a future `expiresAt`. The page records the request ID and completion state in the normal diagnostic report. Therefore a ChatGPT turn can verify that its exact request completed by reading `remoteDiagnostic.lastRequestId` in `sidee-reports/reports/latest.json`.


## Raw-IP HTTP origin A/B test

Sidee exposes a second TV UI on `http://<PC-IP>:8080` specifically to compare the trusted-host path with the direct-IP pattern reported by some VIDAA 9 users.

The comparison is:

- A: `https://vidaahub.com` on port 443;
- B: `http://<PC-IP>:8080` with no DNS hostname involved.

Both serve the same build and use the same backup-protected no-op `fileWrite` test. Reports record `accessContext` (href/origin/protocol/hostname/port/secureContext), server-side request scheme/port, build IDs, API availability, and the exact `fileWrite` result. A different origin is never interpreted as success by itself.

The raw-IP test exists only to determine whether the 503 AppConfig rejection depends on the DNS/origin path. Do not add Nuvio from the raw-IP session unless a separate no-op write first proves `WRITE_ALLOWED_AND_IDENTICAL`.


## Installed-app context trampoline

The raw-IP A/B test proved that DNS/origin alone is not the permission gate on the tested VIDAA 9.60 TV: `fileRead` works from a raw LAN origin but `fileWrite` is still rejected with the same AppConfig 503.

The next bounded experiment uses an app that is already installed by the VIDAA store as the launch context. The TV currently exposes two convenient HTTP apps in `websdk/Appinfo.json`:

- Smartone IPTV — app ID `1470`, host `vidaa.smartone-iptv.com`;
- Duplecast — app ID `1876`, host `vidaa.duplecast.com`.

Sidee's DNS responder now maps those two hosts to the Sidee PC, and Sidee listens on HTTP port 80 in addition to the normal 8080 dashboard. This lets the user launch Smartone or Duplecast from the VIDAA launcher while temporarily receiving the Sidee page inside that installed-app web container.

The report classifies the context as `SMARTONE_APP_CONTEXT` or `DUPLECAST_APP_CONTEXT` and captures the native identity fields before any write test.

### TV procedure

1. Pull and restart Sidee.
2. Set the TV DNS to the Sidee PC IP.
3. Do **not** open Sidee from the normal browser.
4. From the VIDAA home/app launcher, open **Smartone IPTV**.
5. If Sidee loads, confirm the summary shows `SMARTONE_APP_CONTEXT`.
6. Run **Capture Baseline**.
7. Inspect whether `Service identifier` / app identifier are now non-empty.
8. Only then run the backup-protected **Test AppInfo Direct Write** no-op test.
9. Do not use **Add Nuvio to AppInfo** unless the no-op result is `WRITE_ALLOWED_AND_IDENTICAL`.
10. If Smartone does not load Sidee, repeat with **Duplecast**.

After the experiment, restore DNS to Automatic so the original apps resolve normally again.

## Native client context fingerprint

The installed-app trampoline now has a dedicated read-only fingerprint step. When Sidee is opened from the VIDAA launcher through the spoofed Smartone or Duplecast hostname, the fingerprint runs automatically before remote polling starts.

It records and correlates:

- expected launcher app (`1470` Smartone or `1876` Duplecast);
- `navigator.appIdentifier`, `vowOS.service.getIdentifier()`, `vowOSContext.getAppIdentifier()` and `getAppId()`;
- Role ID / Customer ID;
- `Hisense_SupportAppConfig()`;
- bounded own data-property metadata already present on `vowOS.service`, `vowOSContext`, `navigator` and `window`.

Unknown accessors are not invoked. Fields whose names look like tokens, secrets, credentials, auth/cookies, keys, signatures, certificates, nonces or sessions are redacted instead of copied into the report.

The classification is deliberately descriptive: `INSTALLED_APP_IDENTITY_MATCH`, `INSTALLED_APP_IDENTITY_PRESENT`, `INSTALLED_APP_METADATA_PRESENT`, `INSTALLED_APP_CONTEXT_ANONYMOUS`, `BROWSER_IDENTITY_PRESENT`, `APPCONFIG_SIGNAL_ONLY` or `ANONYMOUS_LIKE`.

This fingerprint does **not** claim that matching an app ID grants permission. The previous Identifier Write-Gate Lab already proved that changing only the JavaScript identifier string to installed-app IDs is insufficient. The useful comparison is now whether launching through a real store-installed app container changes the native identity/config state and, separately, whether the backup-protected no-op AppInfo write changes from the same 503 rejection.

## Identifier Write-Gate Lab

After raw-IP and `vidaahub.com` produced the same AppConfig 503 on direct `fileWrite`, the decisive identity test now targets the protected operation itself rather than comparing `fileRead` responses.

The lab creates one immutable AppInfo backup, performs a baseline no-op `fileWrite` with the native/current identifier, then tests at most 6 concrete identifiers gathered only from runtime identity fields, current AppInfo entries and installed-app metadata. Every candidate writes the exact same raw registry bytes, immediately reads them back, and restores `vowOS.service.getIdentifier` in `finally`.

The lab stops immediately if a candidate changes the permission response or if the registry readback is not identical. It never adds Nuvio. Possible conclusions include `IDENTIFIER_AFFECTS_WRITE_GATE`, `IDENTIFIER_STRING_NOT_SUFFICIENT`, `NO_REAL_IDENTIFIER_AVAILABLE`, `BASELINE_WRITE_ALLOWED`, `REGISTRY_CHANGED_ABORTED`, and `INCONCLUSIVE`.

The remote version is a separate explicit build-bound workflow (`runIdentityWriteGateLabV1`) and is not classified as read-only.


## Installed-app bootstrap fallback

If launching Smartone IPTV or Duplecast with the TV DNS pointed to Sidee leaves the original app on an endless loading spinner and no Sidee session report appears, the failure is before the normal `web/app.js` UI executes.

Sidee therefore serves a dependency-free inline bootstrap page for the two installed-app hostnames on HTTP port 80. The bootstrap:

- is returned for any non-API path on `vidaa.smartone-iptv.com` and `vidaa.duplecast.com`;
- records a server-side request hit immediately;
- captures only read-only native identity/capability fields;
- posts the capture to `/api/app-context-bootstrap`;
- saves/syncs a normal Sidee session report even though the full UI was never loaded;
- performs no install, uninstall, setter, file write or guessed native call.

The PC can inspect the last server-observed trampoline request at `/api/app-context/last-hit`.

After pulling this build, Sidee must be restarted so the new HTTP/80 handler is active. Then launch Smartone or Duplecast from the VIDAA launcher while the TV DNS points at the Sidee PC.


### Windows TCP/80 fix — 2026-09-26

The installed-app trampoline uses the apps' real HTTP StartCommand on the default TCP port 80. A Windows-specific launcher bug was found: `start-windows.bat` opened UDP/53, TCP/443 and TCP/8080 in Windows Firewall, but not TCP/80. That can leave Smartone/Duplecast on the VIDAA loading spinner even while the normal Sidee browser UI works correctly.

The Windows launcher now also creates the `Sidee HTTP TCP 80` inbound firewall rule. The TCP/80 listener is also treated as critical: if it cannot bind (for example because another local service already owns port 80), Sidee prints a clear error and stops instead of silently continuing with a broken installed-app test.

For a valid trampoline run the terminal must show:

```
[HTTP] http://0.0.0.0:80 (installed-app context)
```

If the launcher still spins after that, the DNS/HTTP transport tracing in the current build should distinguish “TV never resolved the app hostname” from “DNS reached Sidee but HTTP never arrived” from “the bootstrap page executed”.


## Installed-app AppInfo write-gate test — 2026-09-26

The Duplecast trampoline has now proven a real installed-app native context on the tested TV:

- access mode `DUPLECAST_APP_CONTEXT`;
- `appId = "1876"`;
- `navigator.appIdentifier = {"appid":"1876","md5":"ba9a56ce0a9bfa26e8ed9e10b2cc8f46","permissions":""}`;
- `vowOS.service.getIdentifier() = "UMdO2+D/C/NrEj31J4Ylxw=="`;
- `vowOSContext.getAppIdentifier()` returns the same native identifier;
- `Hisense_SupportAppConfig() = true`;
- `HiUtils_createRequest` is available even though the high-level install/FileRead/FileWrite wrappers are not exposed.

This confirms that a real launcher-created VIDAA app context carries richer native identity than the previously tested JavaScript override of `getIdentifier()`.

The bootstrap page now exposes an explicit **Run backup-protected AppInfo no-op write** action. It never runs automatically. The action:

1. calls `HiUtils_createRequest("fileRead", {path:"websdk/Appinfo.json", mode:6})`;
2. sends the exact raw registry to Sidee's existing immutable backup endpoint;
3. proceeds only after the server confirms the backup;
4. calls `HiUtils_createRequest("fileWrite", ...)` exactly once with the same raw string;
5. immediately reads AppInfo again;
6. posts the write response and raw readback to `/api/app-context-noop-result`;
7. the server reloads the immutable backup and independently compares the readback bytes/hash/count;
8. the same app-context session report is updated and synced to `sidee-reports`.

Possible classifications are `WRITE_ALLOWED_AND_IDENTICAL`, `WRITE_DENIED`, `WRITE_CHANGED_CONTENT`, `READBACK_FAILED`, or `INCONCLUSIVE`.

No Nuvio entry is added by this test. A successful native-context no-op write is still only a capability result; app addition remains a separate later decision.


## Native app-context bridge-source capture — 2026-09-26

Smartone IPTV and Duplecast both produced the same protected-write result from their genuine launcher-created app contexts: native identity present, `navigator.appIdentifier` containing the real app ID plus an MD5 and `permissions:""`, `Hisense_SupportAppConfig() === true`, but exact no-op `HiUtils_createRequest('fileWrite', ...)` still rejected with code 503 and unchanged readback.

This rules out hostname/origin alone, a simple app-ID override, and merely launching inside an installed store app as sufficient explanations.

The installed-app bootstrap now also captures, read-only, bounded function source/descriptors for:
- `HiUtils_createRequest`;
- `vowOS.service.syncExecute`;
- `vowOS.service.getIdentifier`;
- `vowOS.service.executeHttpRequest`;
- `vowOSContext.init`;
- `vowOSContext.getAppIdentifier`;
- `vowOSContext.getAppId`.

It also records bounded property names for `vowOS.service` and `vowOSContext`, excluding names that look like tokens, credentials, cookies, keys, signatures, certificates, nonces or sessions. No unknown accessor is invoked by this source capture.

Goal: determine whether the JavaScript bridge passes only explicit `api + args` or whether native client/AppConfig metadata is attached out-of-band below the visible JavaScript identifier layer.


## Bridge authorization finding — 2026-09-26

A genuine launcher-created Duplecast context exposed the JavaScript bridge sources. The visible request path is now verified:

```text
HiUtils_createRequest(type,msg)
  -> vowOS.service.syncExecute('hiutils', {api:type,args:msg})
  -> vowOS.service.executeHttpRequest(...)
  -> POST https://localhost:9888/service/hiutils
     header: identifier = vowOS.service.getIdentifier()
     body: JSON.stringify({api,args})
```

`vowOS.service.getIdentifier()` delegates to native `vowOSContext.getAppIdentifier()` when the runtime app context exists. No MD5, permissions object, origin metadata or AppInfo record is visibly appended by these JavaScript wrappers.

The real Duplecast and Smartone launcher contexts both had:
- correct real app IDs;
- distinct app MD5 values in `navigator.appIdentifier`;
- non-empty native app/service identifiers;
- `Hisense_SupportAppConfig() === true`;
- `permissions:""`;
- the same code 503 AppConfig rejection for exact no-op `fileWrite`.

Therefore the current evidence points to permission resolution below the visible JavaScript wrapper layer, keyed at least by the native identifier/session context. A valid installed-app identity is not equivalent to write permission.
