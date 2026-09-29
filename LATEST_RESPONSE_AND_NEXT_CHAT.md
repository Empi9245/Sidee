# Sidee — full capture now starts; UI polling fixed

Data: 2026-09-29

Latest real report on `sidee-reports`:
- session `sidee-20260929-171309-a335`
- `fullNetworkCapture.status = CAPTURING`
- `startedAt = 2026-09-29T15:14:58Z`
- ETL / PCAPNG / TXT paths were created
- `error = null`
- preflight is clean
- pktmon reports active capture on network adapters
- current Sidee-TV filter shown by pktmon is `192.168.137.1`

## Diagnosis

The user's UI appeared stuck on `STARTING`, but the backend had already transitioned to `CAPTURING`.

Cause: the web UI refreshed Full Network Capture once after the ARM request and once on page load, but did not poll the capture endpoint afterward. If the asynchronous backend thread moved from STARTING to CAPTURING after the ARM response, the page stayed visually stale.

## Fix on main

Commit `a190ad64d4957d84a6bad709ec0413b98c342818`:
- Full Network Capture now polls `/api/full-network-capture` every ~1.2 s.
- STARTING / CAPTURING / ERROR transitions become visible without reloading.

## Important next check

The latest capture is using filter IP `192.168.137.1`.

Do not yet assume this is the TV client. On the next clean test, use the IPv4 address shown in the TV's own network settings in the Full Network Capture input. If the TV IP is different from `192.168.137.1`, enter the TV IP explicitly.

Then:
1. pull/restart Sidee as Administrator;
2. arm capture with the TV IPv4 explicitly entered;
3. confirm UI reaches CAPTURING;
4. play YouTube for ~15-20 seconds;
5. stop/analyze;
6. inspect ETL/PCAPNG/TXT size, packetRecords, httpsPacketRecords and topologyClassification.

Do not reinstall Duplecast until normal TV HTTPS is confirmed visible in the full capture.
