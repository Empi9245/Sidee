# Sidee — Nuvio persistent-app feasibility assessment

Date: 2026-09-30, Europe/Rome.

Read `VIDAA_FEASIBILITY.md` for evidence, three-route evaluation, dependencies,
decisive tests, abandonment criteria, acceptance status and source links.

## Objective and outcome

User wants Nuvio on Hisense VIDAA Q0707 as an app launched from the TV launcher,
operated entirely by arrows/OK/Back, persistent after reboot, with Sidee and
the local UI host off during normal use. Internet content/account services are
allowed; the user does not want to operate UI hosting. Devkit and Superdesign
are excluded. Browser fullscreen and service-worker cache are insufficient.

**No evaluated route currently proves all these requirements.** There is no
demonstrated authorized local Nuvio package/import workflow on this firmware.
Hosted registration remains dependent on UI hosting. A provider-managed UI
could remove the user's hosting obligation, but no such VIDAA Nuvio deployment
was verified; it is a distinct conditional route, not a local-install result.

## Repo and report state

- Initial Sidee `main`: `89acbe5ada4ae221773fd426c65918bd786dbe6e`.
- Fetched and fast-forwarded to `7c4700ea5e239925ad4531191e0de92124cfc09a`
  before this assessment; read the added runtime handoff and auto-capture work.
- Existing staged addition `control/request.json` contains disabled requests.
  Preserve it; do not include it in unrelated commits or run it.
- Nuvio `main`: `1f1ad284a292c06b0ed6b045dd1e1f3177666d1b`; clean, unchanged.
- Latest local report: `sidee-session-20260929-194224-f686.json`, updated
  `2026-09-29T19:10:18Z` (21:10:18 Italian time), build `app-5dbeec3fbd21`,
  `buildMatch:true`. DNS-only; no package/offline verification.
- Remote report commit `f8dee5d5ced6fde8b7d936a92bec45bd423643fb`,
  29 September 21:09:38 +0200; same session, updated `19:09:35Z`.
- Report does not include Git HEAD. Recomputed build digest with Windows CRLF
  matches code commits `f5b5a9b` and `89acbe5`; cannot distinguish doc-only commits.
  Do not assume it ran the newer `c895f314` auto-capture code.
- Browser report `sidee-session-20260929-191916-046b.json`: no keyboard or
  hiWebOsFrame bridge, key routing not attempted, zero remote events,
  automatic install skipped because install APIs were unavailable.
- Saved capture `sidee-net-20260929-173911`: 384 decoded IPv4, 382 HTTPS
  records, topology `FILTERED_FLOW_VISIBLE_AFTER_NAT`. HTTPS visibility is
  solved. TLS does not reveal package bytes/path/storage.

## Route evidence

1. **Local package:** real system packages and pkgmgr exist, but no authorized
   package format/staging/import for a user-owned Nuvio app is known. Nuvio's
   packager creates a plain JSZip web archive, without a demonstrated VIDAA
   package/signing/install workflow. Do not invent names or invoke pkgmgr install.
2. **Hosted launcher registration:** Duplecast's 26 September original registry
   has remote URL/StartCommand, `packaged:0`, empty appBundle/configUrl. Native
   Duplecast identity is not proof of local resources. There is no fresh
   before/after storage inventory proving what the 29 September install retained.
   Nuvio installer sends a URL, not ZIP/resources, and still has callback-0
   false-success wording. PC/IP or user-managed public hosting fails the goal.
3. **Persistent container:** Duplecast/SmartOne documentation describes playlist
   players, with no local HTML app import in the checked pages. MSX documents
   hosted JSON/link/plugins; interaction iframes receive no input. MSX is not
   in the observed 61-app inventory and availability here is unverified.
   No documented local persistent Nuvio-resource container was found.

## Changes in this delivery

- Added the feasibility assessment; updated README/context/handoff.
- Empty default spoof_domains: no automatic SmartOne hostname substitution.
- `store_download_capture.auto_arm_on_start:false`: no automatic old capture.
- Preserved diagnostic code and existing staged work; Nuvio code unchanged.
- No server restart, TV mutation, new probe, capture, install or playback claim.

The existing Sidee UI startup probes remain in code. Do not open/restart the
TV page merely to generate another report for this assessment.

## Next discriminating step

Identify a documented authorized import/distribution path for Q0707 that can
store a user-owned app locally without devkit. VIDAA's current content-partner
channel is documented, but package eligibility/import remains unconfirmed.
Do not send vendor/maintainer messages without human authorization.

Only if that precondition is satisfied, implement the smallest app with its
own ID, verify local resource provenance and all five TV acceptance checks,
then integrate Nuvio and test authorized playback. For a container, require
documented import/storage/JS/input first. If only URLs/playlists/cache are
available, abandon the local route under current constraints.

A further Duplecast experiment must distinguish storage/host dependency with
documented metadata and a cold-start test. SNI or large/small TLS flows alone
cannot prove a downloaded package. Do not reinstall Duplecast just for those.
