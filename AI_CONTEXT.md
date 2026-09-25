# Sidee — AI Context / Research Notes

> Read this file before doing new VIDAA research or changing the installer.
> Goal: avoid repeating already completed research, tests, and conclusions.

Last updated: 2026-09-25

## Project

Repository: `Empi9245/Sidee`
Branch: `main`

Sidee is a standalone local diagnostic/installer lab for Hisense VIDAA TVs.
It is intentionally separate from Nuvio TV.

Primary target app during current testing:
- Repo: `Empi9245/nuviotvsmart`
- App ID: `nuviodebug`
- App name: `Nuvio TV`
- Test URL: `http://192.168.1.5:4173/?wrapper=vidaa`
- Icon: `http://192.168.1.5:4173/assets/images/icon.png`

Sidee provides:
- DNS spoof for `vidaahub.com`
- HTTPS host on port 443
- dashboard/fallback on port 8080
- VIDAA API discovery
- legacy and V2 install tests
- OMI launcher refresh
- installed-app verification
- read-only `websdk/Appinfo.json` inspection
- JSON reports saved on the PC

## Tested TV

Real hardware used for the current research:

- Brand: Hisense
- Model: `50E70LEVS_0003`
- Firmware: `V0000.09.60A.Q0707`
- OS: `VIDAA U09.60`
- VIDAA API version: `3.0.1`
- Chipset: `MTK9603`
- Runtime: Chromium 111
- Browser reported by VIDAA: `odin`
- Region: `EU_A`
- Country: `ITA`
- Panel: `3840*2160`
- TV LAN IP during tests: `192.168.1.10`

The Sidee page was successfully executed from:
- `https://vidaahub.com/`
- origin: `https://vidaahub.com`

Therefore the DNS/HTTPS setup is confirmed to reach the privileged VIDAA browser context on this TV.

## Important APIs confirmed on this firmware

The firmware exposes, among many others:

- `Hisense_installApp`
- `Hisense_installApp_V2`
- `Hisense_uninstallApp`
- `Hisense_getInstalledApps`
- `Hisense_FileRead`
- `Hisense_FileWrite`
- `Hisense_SupportAppConfig`
- `HiUtils_createRequest`
- `omi_platform`
- `opera_omi`

`HiUtils_createRequest` is implemented by the firmware as a wrapper around:

`vowOS.service.syncExecute('hiutils', { api: type, args: msg })`

Do not assume an API is usable just because the JavaScript function exists.

## Key discovery: install callback 0 is NOT proof of installation

Earlier tools, including simple installers based on `Hisense_installApp`, may report success when the callback returns `0`.

On this firmware this is misleading.

Sidee now verifies installation using:
1. `Hisense_getInstalledApps`
2. read-only `websdk/Appinfo.json`
3. before/after snapshots
4. internal HiUtils tracing where possible

A callback of `0` must be treated only as "request accepted by the JavaScript wrapper", not as "app installed".

## Real install test results

Both install methods have been tested against the real Nuvio target.

### Legacy: `Hisense_installApp`

Observed behavior:
- JavaScript callback: `0`
- wrapper return value: `false`
- launcher refresh through OMI: attempted
- Nuvio absent from `Hisense_getInstalledApps`
- Nuvio absent from `websdk/Appinfo.json`
- final verification: `false`

The internal call reaches HiUtils and fails at:

`installApplication`

with:

- `ret: false`
- `code: 503`
- message: `client request permission check error, please check appconfig`

### V2: `Hisense_installApp_V2`

Observed behavior is effectively the same:
- callback can still report `0`
- function return value is `false`
- internal `installApplication` call fails
- app is not added to installed apps
- app is not added to `Appinfo.json`

Real internal error:

`client request permission check error, please check appconfig`

Code:

`503`

## Current main conclusion

The current blocker is NOT:

- Nuvio URL
- Nuvio application code
- wrong icon
- wrong app ID alone
- missing OMI refresh
- failure to reach `vidaahub.com`
- absence of the install APIs
- difference between legacy and V2 install APIs
- total lack of HiUtils access

The blocker is the firmware's internal client permission / appconfig check for the privileged `installApplication` operation.

The TV permits useful read access, including reading `websdk/Appinfo.json`, but rejects the install write path.

## Relevant external research already checked

### Stremio Hisense installer

Repository:
`Stremio/stremio-hisense-install`

Useful findings already incorporated:
- uses `vidaahub.com`
- uses `Hisense_installApp`
- sends an OMI `AllAppsUpdate` message after install
- historically assumes callback `0` means success

Do not copy that success assumption.

### vidaa-edge

Repository:
`weinzii/vidaa-edge`

Useful findings already incorporated:
- broad VIDAA API discovery
- legacy install API
- V2/install-related research
- Appinfo read/write research
- function-source discovery

Relevant issue:
`weinzii/vidaa-edge#30`

That issue reports the same firmware-family behavior:
`client request permission check error, please check appconfig`

Reported affected VIDAA 9.60 firmwares include examples such as:
- `V0000.09.60F.Q0528`
- `V0000.09.60C.Q0516`
- `V0000.09.60A.Q0602`

Our tested firmware:
- `V0000.09.60A.Q0707`

This strongly suggests the permission restriction is firmware-family behavior, not a Nuvio-specific failure.

## Important implementation notes

Current Sidee main includes:
- automatic correction when icon URL accidentally equals app URL
- separate Legacy and V2 install buttons
- HiUtils tracing around install calls
- Appinfo snapshots before/after
- verification after callback and launcher refresh

Current known good Nuvio icon path:
`/assets/images/icon.png`

Do not use the Nuvio page URL itself as the icon.

## Things NOT to repeat blindly

Do not spend time re-testing these assumptions unless new evidence appears:

1. "Try callback 0 again" — already disproved as a success signal.
2. "Maybe V2 works when legacy does not" — both reach the same permission failure.
3. "Maybe OMI refresh is missing" — refresh already runs; app was never registered.
4. "Maybe the icon is invalid" — corrected and retested.
5. "Maybe Nuvio URL is unreachable" — Nuvio is reachable on the LAN and serves the VIDAA build.
6. "Maybe Sidee is not really running under vidaahub.com" — confirmed it is.
7. "Maybe Appinfo cannot be read" — on this specific TV it can be read.
8. "Maybe direct fileWrite should be tried immediately" — do not jump to this.

## Safety / scope

Do NOT automatically:
- force-write `websdk/Appinfo.json`
- corrupt or replace launcher databases
- call `Hisense_ResetDevice`
- use service-menu tricks
- downgrade firmware
- modify bootloader/system partitions
- bypass signing through destructive system changes

Presence detection, source inspection, read-only file reads and non-destructive probes are acceptable.

Direct Appinfo writes remain intentionally disabled in Sidee unless a later device-specific method is understood and explicitly opted into with safeguards.

## Best next research direction

The next useful work is NOT another blind install attempt.

Investigate the appconfig / permission layer safely.

Recommended next probe:
- enumerate globals/functions containing:
  - `appconfig`
  - `permission`
  - `access`
  - `client`
  - `config`
  - `installApplication`
- capture sources where available
- inspect `Hisense_SupportAppConfig()`
- inspect relevant read-only HiUtils requests
- inspect the browser/client identity used by `vowOS`
- compare allowed read operations vs blocked install operations
- look for documented appconfig metadata already loaded in the page/runtime
- avoid speculative writes

The goal is to answer:

"What exact appconfig/client permission does VIDAA 9.60 require for `installApplication`, and is there a supported/exposed way for a vidaahub.com client to obtain it?"

## Reports already produced during this investigation

Local report filenames seen during testing:

- `vidaa-20260925-174651-856214.json` — initial read-only API scan
- `vidaa-20260925-180251-277424.json`
- `vidaa-20260925-180304-691675.json`
- `vidaa-20260925-180324-294314.json`
- `vidaa-20260925-181319-290491.json` — V2 install test
- `vidaa-20260925-181332-307152.json` — Legacy install test
- `vidaa-20260925-181401-996903.json`
- `vidaa-20260925-181411-919592.json`

Reports may remain local because `reports/*.json` can be ignored by Git. The conclusions above summarize the important findings so another AI does not need those files just to reconstruct the investigation.

## Instructions for future AI agents

Before making changes:
1. Read this file.
2. Read the current `README.md`.
3. Check current `main` HEAD.
4. Inspect current `web/app.js` before modifying install logic.
5. Preserve the distinction between JavaScript callback success and verified installation.
6. Prefer evidence from the exact TV/firmware over assumptions from older VIDAA versions.
7. Do not reintroduce an invented public Nuvio URL.
8. Keep Sidee standalone from Nuvio.

When a new report is provided, compare it against the known baseline above rather than restarting the investigation.
