# Sidee — next test: recover pktmon, then prove normal TV HTTPS

Data: 2026-09-29

Latest real report:
- session `sidee-20260929-164523-4fb4`
- `fullNetworkCapture.status = ERROR`
- `startedAt = null`
- no ETL / PCAPNG / TXT paths
- no capture summary
- error: `pktmon start failed: Monitoraggio pacchetti già avviato.`

## Diagnosis

This run was not an empty capture. **pktmon never started.**

The Sidee preflight was language-dependent: it looked for English words in
`pktmon status` before deciding to call `pktmon stop`. On Italian Windows an
old Sidee capture could therefore remain alive after a forced Sidee restart.
The stale `Sidee-TV` filter could be removed while the pktmon collection itself
kept running, causing the next start to fail as already active.

## Fix on main

The capture preflight now:
- stops first when the only filter is `Sidee-TV`, without parsing localized prose;
- also recovers a no-filter orphan when status points to a Sidee ETL under
  `captures/sidee-net-*`;
- never stops/removes an unrelated ETL capture or unrelated filters;
- stores bounded preflight diagnostics in `fullNetworkCapture.preflight`.

Do not change `--comp nics` yet. NIC/ICS visibility has not actually been
tested because the failed run never entered `CAPTURING`.

## Next test — no Duplecast

1. `git pull`
2. restart Sidee as Administrator
3. TV DHCP/IP automatic and DNS automatic
4. keep the TV on the intended Windows hotspot/ICS/routed path
5. note the TV IPv4 and enter it in Full Network Capture
6. press **Arm / Start capture**
7. verify the UI reaches **CAPTURING**
8. open YouTube on the TV and play a video for about 15–20 seconds
9. press **Stop & analyze capture**
10. say `fatto topology`

What to inspect next:
- `startedAt` must be non-null;
- ETL / PCAPNG / TXT sizes;
- `packetRecords`;
- `httpsPacketRecords`;
- `topologyClassification`;
- `preflight`.

Interpretation:
- files > 0 but `packetRecords = 0` -> parser problem;
- capture really starts but normal TV HTTPS is absent -> then research
  pktmon + Windows ICS/NAT components and test a bounded topology-discovery
  capture, likely including components beyond `nics`;
- normal HTTPS visible -> only then repeat an official Store download/install
  capture.

The latest Store/DNS report contains no new `nativeInstallApiSurface` evidence.
Keep the prior `vowOS.store/pkgmgr` conclusions; do not repeat those probes
without new evidence.
