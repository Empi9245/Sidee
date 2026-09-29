# Sidee — pktmon packets exist; validate parser + automatic TV binding

Data: 2026-09-29

Latest completed capture is NOT empty:
- session `sidee-20260929-172209-014d`
- capture `sidee-net-20260929-172248`
- ETL 62,270 bytes
- PCAPNG 72,912 bytes
- TXT 425,292 bytes
- pktmon conversion: 340 total packets, 340 formatted, 0 missed
- old Sidee result: `packetRecords=0` / `NO_PACKET_RECORDS`

Cause:
1. Sidee used `etl2txt --brief` but the parser depended on `OriginalSize`;
2. the filter used `192.168.137.1`, which may be the Windows ICS/hotspot host/gateway rather than the TV.

Fixes now on main:
- full/non-brief pktmon text conversion;
- fallback parsing of IPv4 packet lines when `OriginalSize` is absent;
- separate `parsedIpPacketLines` and `tvMatchedPacketRecords`;
- new `CAPTURED_BUT_TV_IP_NOT_VISIBLE` classification;
- UI recommends blank TV IPv4 for automatic binding to the actual DNS client observed from the TV.

Duplecast install DNS sequence already captured:
`appstore-vidaa.vidaahub.com -> tvmodules-vidaa.vidaahub.com -> detail-ui-eu.vidaahub.com -> vidaa.duplecast.com -> files.duplecast.com`
with `targetDomainHit=true`.

## Next test — do NOT reinstall Duplecast yet

1. `git pull`
2. restart Sidee as Administrator
3. leave TV IPv4 EMPTY
4. press Arm
5. open VIDAA Store on TV to trigger automatic client binding
6. confirm CAPTURING
7. play YouTube 15-20 seconds
8. Stop & analyze
9. reply `fatto parser`

Next inspection:
- packetRecords
- parsedIpPacketLines
- tvMatchedPacketRecords
- httpsPacketRecords
- topologyClassification

Only after normal TV HTTPS is visible should Duplecast be reinstalled/captured again.
