# Sidee

## Installazione VIDAA v2 integrata

Il pacchetto `Kimi_Agent_Installazione Hisense Vidaa 9.zip` è integrato come
flusso isolato a tre fasi. Avvia `start-windows-vidaa-v2.bat`, quindi usa sulla
TV **Analizza → Installa → Verifica dopo riavvio**. Il target viene letto dalla
sezione `nuvio` di `config.json`; il registro deve essere letto e salvato nel
report prima che il pulsante di scrittura venga abilitato. La precedente verifica
senza scritture resta disponibile tramite `start-windows-vidaa-check-v2.bat`.
Dettagli e risultati possibili: [VIDAA_INSTALL_V2.md](VIDAA_INSTALL_V2.md).

The collector buttons now initialize even when the TV browser defines a module
shim; Node exports apply only outside a browser. Control/upload requests reject
redirects and omit credentials, with an error shown in the page. Buttons prevent
default navigation. HTTP requests from the owner's TV for root and script were
observed on1Oct2026; no source receipt yet. The isolated collector now serves
the vidaa-edge-style HTTPS route on port 443 with a local self-signed
`vidaahub.com` certificate.

LAN DNS diagnostics keep separate target query/reply counters for up to32 clients.
`repliesSubmitted` means the local socket sent a reply, not that the TV received
or used it. Only vidaahub target events are recorded; ordinary query names remain
unlogged. A locked diagnostic file no longer interrupts DNS replies, and rapid
queries retain both PC and TV client metrics. Tests cover real UDP/TCP delivery
with a simulated locked status file. Current known TV IP .1.10 and primary DNS
.1.5 are owner-confirmed. Runtime PID/hash are in the local DNS status file.

The isolated HTTPS collector records minimal access diagnostics in `/status`
(`httpAccess`) and local ignored `reports/bridge-domain-http-status.json`.
Separate TCP connection/request counts and known-page/script counts distinguish
DNS visibility from page delivery. Private IPs only, maximum 32 clients; no query
strings, request bodies, cookies or private TLS payload capture. No TV API is called by this
diagnostic. A null collection receipt does not imply the page was never opened.

Current connection confirmed by owner: **TV and PC are on the router LAN**.
Set TV primary DNS to **192.168.1.5**, reopen the Browser and visit
**https://vidaahub.com/**, then press **Raccogli una volta**.
`start-windows.bat` now starts/reuses `lan_dns.py` before the collector:
UDP/TCP only on 192.168.1.5:53, clients 192.168.1.0/24, vidaahub.com → this PC,
ordinary DNS via router 192.168.1.1. No Store/native/SDK/capture workers or
other-name query logging. ICS remains running. PC DNS/forwarding checks passed;
TV receipt required. Hotspot .137.1 advice below is historical for this setup.

The launcher uses these known local addresses; update its explicit arguments
if the PC address/router subnet changes. An existing matching DNS service is
reused via bounded local health checks; foreign/stale services remain intact.

Windows startup fixed: `start-windows.bat` now opens the isolated collector on
HTTPS/443 after the isolated LAN DNS. It does not start Store workers, alter firewall rules or
stop existing processes. A second launch reuses the same matching receiver and
receipt. The previous launcher killed all Sidee instances and then collided
with Windows ICS DNS. Keep ICS running. Current process provenance is in
https://192.168.1.5/status; older PID references below are historical.

For a TV connected to **this PC's Windows hotspot**, primary DNS is
**192.168.137.1**, where ICS actually answers vidaahub.com with 192.168.1.5.
The Ethernet IP 192.168.1.5 serves the collector but does not answer DNS in this setup.
After a TV DNS change, close/reopen the Browser and use https://vidaahub.com/.
This instruction is specific to the hotspot; TV router-network settings are
not confirmed. A TV "name not resolved" report does not mean the collector ran.

The fixed BAT and a second-launch reuse have been verified on this PC. Current
collector PID2312, receipt null at verification. Historical :8080 receiver is
stopped; its restart was blocked by automatic review pending specific user
approval. It is independent of this collector; old reports remain local.

Subsequent explicit owner approval received: historical :8080 receiver restored
as PID9552, existing report unchanged, no new collection. Collector PID2312 and
ICS remain intact; the earlier approval block is resolved.

Current collector entry: **https://vidaahub.com/**, served at `/` on HTTPS/443 by
`python sidee.py --bridge-source-check --check-port 443 --check-https`. The owner explicitly
requested restoration of the previous vidaa-edge-style HTTPS context. Existing Windows ICS DNS now returns the
current PC IP 192.168.1.5 after repair of the stale hosts entry (raw backup kept
locally); ICS and post-Store receiver are preserved. PC domain/root HTTP 200
verified historically; the current route is HTTPS. TV receipt still required: open the URL and click Raccogli una volta.
Check receiver state at https://192.168.1.5/status. No native probes or SDK
execution. `setup_bridge_domain.ps1` is a guarded one-time repair for that exact
stale hosts entry, using the expected full-file SHA256; do not rerun after repair.
The previous :8082 receiver and opening instructions below are historical.

Latest TV result: the collector URL on :8082 does not open (user reports
«impossibile»). Receiver remains active with no receipt. That opening instruction
is withdrawn because TV domain routing to the receiver was not verified.
Bare vidaahub.com does not automatically load this local collector. Details in
[the acquisition record](research/bridge-source-acquisition-20260930.md).

## Targeted loaded-source acquisition — 30 September 2026

New isolated mode: `python sidee.py --bridge-source-check --check-port 8082`.
It collects only after an explicit click, using script tags plus resource timing
to find already-loaded, browser-readable scripts missing from past excerpts.
No native calls, SDK execution, inventory, DNS/TLS, historical startup probes or
Git upload. Local reports contain source/build/report hashes and completeness.
[Scope, context, checks and access blocker](research/bridge-source-acquisition-20260930.md).
vidaahub remains the preferred context; this mode does not create domain routing.
HTTP/8082 and LAN observations are distinguished from historical HTTPS/443.
Receiver readiness is verified; **no new TV receipt or installation yet**.

## Current diagnosis: legacy, V2 and upstream New

[Installation-method diagnosis](research/install-methods-q0707-20260930.md):
the TV's captured legacy/V2 wrappers call the same installApplication backend.
Both saved attempts read successfully then receive AppConfig 503; callback 0
does not establish success. V2's object-type guard was not the failing step.
vidaa-edge's New (File System) method is a separate direct registry-write path,
whose write capability was already denied in the saved vidaahub no-op test.
No new TV operation or working installation fix; backend traces/source hashes
are now included in the reproducible comparison. These URL-registration paths
do not transfer Nuvio's resources to the TV.

Latest direction: study the captured VIDAA code locally, with no further online
research. The user already tried hisense://debug; do not request it again.
[Offline package-wrapper audit](research/vidaa-install-contract-20260930.json)
confirms that package success can mask failed launcher registration. It executes
two reviewed source bodies with a fixture transport, not TV operations.
The captured wrappers do not supply a verified own-package stager/format or the
system service's AppConfig decision implementation. No working install fix found.

## Current correction: vidaa-edge context

Read [the source review](research/vidaa-edge-context-review-20260930.md).
vidaahub is the context used for API exposure in vidaa-edge, not a public
installation portal. The previous instruction to open its public site with
automatic DNS was mistaken and withdrawn. Reachability of that public root does
not decide the toolkit mechanism. API exposure and write authorization differ;
the saved Q0707 vidaahub reports already show exposed APIs and AppConfig denial.

The secondary Nuvio UI/remote trial was prepared and then stopped, with no TV
result; [protocol and limits](research/tv-acceptance-20260930.md). Its code is
preserved for future functional checks, not a replacement for this investigation.
No inventory/capture/install/write was repeated. Public documentation is not a
prerequisite for every observation.

## Current handoff — vidaahub context investigation

Next-chat prompt: [NEXT_CHAT_PROMPT.md](NEXT_CHAT_PROMPT.md). Complete current
state: [LATEST_RESPONSE_AND_NEXT_CHAT.md](LATEST_RESPONSE_AND_NEXT_CHAT.md).
The priority investigation is now recorded in
[research/vidaahub-context-20260930.md](research/vidaahub-context-20260930.md), with
a reproducible [six-report comparison](research/vidaa-context-comparison-20260930.json).
Published generation-dependent bridge access does not establish Q0707 write
permission; no documented replacement origin or own-app import was found.
PC hosts still maps vidaahub.com to a private IP, so its ordinary HTTPS timeout
is not a public-site test. Public DoH returned NODATA A/AAAA at this check.
A different permission-granting origin is a hypothesis, not an established
import path. API availability, installation permission and persisted resources
are separate questions. Do not replace this question with another LAN snapshot.
The real inventory response has arrived; earlier pending states are historical.

## Current assessment — persistent Nuvio app on Q0707 (2026-09-30)

Read [VIDAA_FEASIBILITY.md](VIDAA_FEASIBILITY.md) and
[LATEST_RESPONSE_AND_NEXT_CHAT.md](LATEST_RESPONSE_AND_NEXT_CHAT.md) before
running any procedure below. **No route currently proves all requested Nuvio
app requirements without devkit:** launcher launch, full remote navigation,
reboot persistence, and use with Sidee/local UI host off, without user-managed
UI hosting. Browser fullscreen and service-worker cache are insufficient.

The model is now confirmed as **Hisense 50E77NQ**. Further source research found
official Nuvio 1.2.1 TV packages only for Tizen/webOS, an upstream explanation of
the hosted VIDAA port, and documented MSX support for VIDAA U6+ but no proven
persistent local-app import. See the follow-up section in the assessment.

Latest constraints: **no VIDAA contact/partner onboarding and no Media Station X**.
The user confirms MSX is in their TV Store but declines it. The off-TV audit in
[research/](research/README.md) shows its reviewed BlobService retains resources
only in its current instance; this is not a TV reboot test. The official Nuvio
wrapper points at `web.nuvioapp.space`, which returned HTTP 522 in the latest
PC check. A community VIDAA wrapper returns 200 but embeds that same endpoint,
without importing Nuvio locally. The MT9603/U9 software manual describes USB
media and browser shortcuts, not an own-app importer in the inspected sections;
it is for another model/region. No new TV acceptance result or usable candidate.

The Nuvio fork's VIDAA ZIP is an archive of web files, not a demonstrated
installable VIDAA package. Its installer requests URL registration; local source
now treats callback 0 as unverified and explains that no files were copied to
the TV. Packager promises were corrected; no new bundle/ZIP or TV install.
See Nuvio's `VIDAA_STATUS.md`. Duplecast's observed registry entry has a remote
StartCommand and `packaged:0`; its native app identity does not prove local
Nuvio resources. No documented persistent local-app import was found for
Duplecast/SmartOne in the checked vendor documentation.

The latest standard report is a DNS-only session, not package-delivery evidence. The
previous PCAP already confirms 382 HTTPS records after the NAT correction;
there is no need to repeat visibility tests. The assessment records exact
report dates, report-branch commit and reconstructed application build.

Default `spoof_domains` is now empty and `store_download_capture.auto_arm_on_start`
is false. Starting Sidee no longer automatically arms the old Store capture or
redirects SmartOne through custom DNS. Historical tools remain in the code;
they are not an authorized local-app import mechanism. The TV/browser probe
code is unchanged and may still run its existing startup diagnostics if opened.
This assessment does not require opening Sidee on the TV or restarting services.

For import trials, use a permitted package/import feature identified in public
documentation or the TV's normal interface. Direct UI/input tests can precede it.
Evaluate provider-managed hosted-app distribution separately if applicable.
Do not repeat exhausted permission/identity/HSPDK/pkgmgr probes or replace
third-party Store packages. Owner update 2026-10-01: selecting the local
service-bus identifier header is authorized, and the raw-channel identifier
lab supersedes the exhausted assignment-based identity probes (see
AI_CONTEXT.md, AGGIORNAMENTO 2026-10-01).

## Completed isolated TV check — after the Store operation

The result is already received; **do not repeat this inventory**. The instructions
below describe the completed check, not a next step. Its isolated mode used
`python sidee.py --post-store-check` to serve only the inventory page on the
configured PC LAN address and HTTP port (currently `http://192.168.1.5:8080`).
It does not start the historical dashboard, DNS, TLS interception, Git workers,
captures or TV install/write probes. When opened for the completed check,
the page read only `Hisense_getInstalledApps()` and
`vowOS.store.getInstalledPkgs()` if exposed. No SDK injection, identity/origin
override, TV file reads or writes. No custom DNS is needed for this check.

Purpose: obtain current inventory after the 29 September Store operation;
the detailed Duplecast registry snapshot is from 26 September. This is a
targeted freshness check, not another permission or tvbrowser-file probe.
The result can reveal exposed package references/packaging metadata, but missing
fields or an unmatched package are not proof that no app resources are stored.
It does not establish an authorized own-app import procedure.

Target app metadata and package names/versions/paths are saved locally to
`reports/post-store-latest.json` and timestamped `reports/post-store-*.json`.
URL credentials/query strings and unrelated account fields are omitted.
The receiver `/status` reports whether a result arrived; no automatic Git sync.
Reports now include the browser-reported origin/protocol/hostname/secure context
and receiver-observed HTTP Host/Origin headers. These identify the observation
context; they do not confer installation privileges. `192.168.1.5` is the PC's
LAN address, not the TV's localhost. Previous vidaahub-origin tests still returned
AppConfig 503. This isolated mode does not impersonate a VIDAA domain with DNS/TLS.
If neither inventory API is available, the page displays that limitation and
does not save a fake TV result. No Nuvio acceptance test is claimed.

HTTP receiver isolation and denial/error/redaction fixtures passed off-TV.
TV result received on 30 September at 14:09 Europe/Rome: app inventory API
unavailable, package inventory returned 18 system components from the HTTP LAN
origin. No current app/package correlation or local Nuvio importer established.
See [result and limits](research/post-store-result-20260930.md). Do not repeat
this snapshot without a relevant state change.

## Historical toolkit reference and procedures

The sections below describe earlier phases and retained capabilities. Their
"next test", "current priority" and success wording can be obsolete; they do
not override the current assessment or the user's constraints. In particular,
the old vidaahub/SmartOne DNS setup is no longer the default configuration.

Sidee is a **standalone local VIDAA research + web-app installer toolkit**. It is not part of Nuvio TV Smart.

It combines the useful ideas found in:

- Stremio's `stremio-hisense-install`: serving an installer from the trusted `vidaahub.com` browser context, calling `Hisense_installApp`, and refreshing the launcher through the OMI bridge.
- `weinzii/vidaa-edge`: function discovery, VIDAA device diagnostics, `Hisense_getInstalledApps`, and read-only inspection through `HiUtils_createRequest`.

Sidee is deliberately conservative on VIDAA 9. Direct `websdk/Appinfo.json` writes are available only through explicit, backup-protected flows: first an exact no-op write-back capability test, then separately triggered add/restore actions.


## VIDAA Store transport trace — 2026-09-26

The real Q0707 passive DNS test showed that the official VIDAA Store uses several
`*.vidaahub.com` hosts and did **not** show a request for the older
`category-ui.vidaahub.com` endpoint during the observed flow.

The code can trace these hosts separately when explicitly enabled:

- `category-ui.vidaahub.com` — retained for compatibility/reference;
- `detail-ui-eu.vidaahub.com` — observed on the real TV;
- `appstore-vidaa.vidaahub.com` — observed on the real TV;
- `tvmodules-vidaa.vidaahub.com` — observed on the real TV.

However, the real Q0707 test reached TLS SNI on all three observed hosts and
never reached HTTP. The Store UI then displayed a content-load failure. This is
consistent with the TV rejecting Sidee's local certificate before any HTTP
request was sent.

Therefore **Store TLS interception is disabled by default** in `config.json`.
The Store hostnames are no longer included in `spoof_domains`; they remain
visible to the passive DNS discovery instead. This restores normal Store
connectivity while preserving host-level observations.

The multihost trace code and versioned `store-v2` certificate remain in the
repository for controlled experiments, but should not be enabled again unless
there is a trusted-certificate path.

### Passive Store domain discovery

Other scoped VIDAA/Hisense DNS names are still observed without changing their
DNS answers. This is kept separate from the dedicated trace. Hosts promoted to
the dedicated trace are excluded from the generic discovery to avoid duplicate
records.

The Q0707 discovery session `sidee-20260926-201849-a7b2` captured 13 hosts.
Besides the dedicated hosts above, useful discovery-only names included
`home-ui-eu.vidaahub.com` and `recommend-ui-eu.vidaahub.com`.

For the next TV test: pull/restart Sidee, keep the TV DNS pointed at the Sidee
PC, open the official VIDAA Store, browse the home/category view and open one or
more real app detail pages. Do not press Install. The useful result is the
per-host `storeCatalogTrace.hostStats` plus any captured HTTP request paths.

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

This launcher runs the isolated collector on HTTPS/443. Python 3 is required;
the bundled Codex runtime is used when no Python launcher is in PATH.
The local vidaahub route has already been repaired on this PC. Run it as
Administrator if Windows blocks binding to port 443. A second launch preserves an
existing matching collector and its receipt.

### macOS / Linux

```bash
chmod +x start-mac-linux.sh
sudo ./start-mac-linux.sh
```

## TV steps

Current collector: open **https://vidaahub.com/** and press **Raccogli una volta**.
The numbered list below is historical legacy-mode documentation; do not use it
for this collection or rerun the exhausted install/identity/write probes.

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


## Duplecast Store install/download DNS probe

Sidee now includes a passive differential probe for the official VIDAA Store
install/download flow, fixed to the known Duplecast target (App ID `1876`).

The workflow never intercepts Store HTTPS and does not call install APIs itself.
It only timestamps DNS activity already generated by the TV.

Dashboard sequence:

1. **Start capture** before opening the relevant Store flow.
2. Open the Duplecast detail page on the TV.
3. Press **Detail page visible** on the Sidee dashboard.
4. Press **Arm install capture** immediately before selecting Install/Download on the TV.
5. Perform the normal Store Install/Download action.
6. Press **Finish capture** once the Store has produced its result.

The report section `storeInstallProbe` records:
- the Duplecast target identity;
- explicit phase markers;
- bounded DNS events with phase labels;
- the full host snapshot at install arm;
- `contactedAfterInstallArm`: every scoped host queried during the install window, including hosts already seen earlier;
- `newHostsAfterInstallArm`: hosts that first appear after the install arm;
- `queryDeltaAfterInstallArm`: per-host DNS query counts during the install window.

This is deliberately different from HTTPS path tracing: it cannot see encrypted
request paths, headers or bodies. Its purpose is to identify which backend/CDN/
authorization host becomes active specifically when the official Store starts
the download/install workflow.


## Automatic Duplecast install timeline

For the current Store-install phase, no TV-side Sidee dashboard interaction is required.

After Sidee restarts, the DNS server waits for a known Store/UI hostname such as
`home-ui-eu.vidaahub.com`, `layout-ui-eu.vidaahub.com`,
`detail-ui-eu.vidaahub.com`, `category-ui-eu.vidaahub.com`,
`appstore-vidaa.vidaahub.com`, or `tvmodules-vidaa.vidaahub.com`.

When one appears, Sidee starts a bounded DNS timeline tied in memory to that TV
DNS client. From that point it records hostname/query-type timing for the same
client, including non-VIDAA CDN domains. The client IP itself is not persisted.

`vidaa.duplecast.com` is deliberately **not spoofed** during this phase. If the
Store or newly installed app resolves the real Duplecast hostname, the query can
be observed in the automatic timeline without redirecting it to the old Sidee
app-context test page.

The intended test is now simply:
1. pull/restart Sidee;
2. on the TV, open the official Store;
3. find Duplecast and perform the normal install/download without leaving the Store;
4. wait for the Store result;
5. inspect the synced report.

The useful fields are `storeInstallProbe.dnsEvents`,
`storeInstallProbe.allDnsHosts`, `allDnsQueryCount`,
`targetDomainHit`, and `targetDomainFirstSeenAt`.


## Store Static API Mapper

Sidee can inspect public VIDAA Store frontend assets from the PC without
intercepting TV HTTPS traffic.

The mapper uses official TLS and a fixed allowlist of observed VIDAA Store hosts.
It performs bounded GET requests only, sends no TV credentials or cookies, and
extracts API paths plus install/download/package-related string references.

Use the **Run Store API mapper** button in the dashboard. Results are mirrored
into the current report under `storeStaticMap`.


## Full TV Network Capture

On Windows, Sidee can arm a bounded full-packet capture using the built-in
`pktmon.exe`. The TV is filtered by IP, packets are logged with full packet
length, and the ETL is converted locally to PCAPNG and text after stopping.

For this to see the TV's Internet HTTPS traffic, the TV must route through the PC
as a gateway; connecting the TV to Windows Mobile Hotspot is the recommended
test topology. A PC that is only the TV's DNS server cannot normally observe
unicast HTTPS traffic between the TV and the router.

Capture binaries remain under `captures/` and are gitignored. Reports only
contain bounded summary metadata such as byte counts, ports, top peers and a
topology classification.
