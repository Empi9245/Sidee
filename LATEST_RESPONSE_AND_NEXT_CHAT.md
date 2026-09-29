# Sidee — re-analyze the existing Duplecast capture directly from PCAPNG

Data: 2026-09-29

Latest completed capture:
- session `sidee-20260929-173911-7b2f`
- TV auto-bound as `192.168.137.158`
- pktmon captured 1,328 packets
- ETL 170,013 bytes
- PCAPNG 380,504 bytes
- TXT 992,400 bytes
- zero packet loss reported by pktmon
- old TXT parser still produced zero packet lines

This proves capture and TV binding work. The remaining problem is TXT decoding.

Sidee now bypasses TXT and parses the saved PCAPNG directly:
- IPv4/TCP/UDP packet metadata;
- TV matched packet count;
- HTTPS/HTTP/DNS ports;
- top peers;
- topology classification;
- TLS ClientHello SNI hostnames when present.
- parser hotfix `2ad4f66e7e04c2cb7f830dfc2987294e235d08b6` keeps SNI aggregation scoped to PCAPNG analysis.

There is also a new **Re-analyze latest capture** button. It reuses the existing saved capture, so Duplecast does NOT need to be reinstalled for this step.

## Next test

1. `git pull`
2. restart Sidee as Administrator
3. open the dashboard
4. press **Re-analyze latest capture**
5. wait for the result
6. reply `fatto reanalyze`

Next report inspection:
- analysisSource
- pcapPacketBlocks
- pcapIpv4Packets
- tvMatchedPacketRecords
- httpsPacketRecords
- tlsServerNames
- topPeers
- topologyClassification

If `files.duplecast.com`, `vidaa.duplecast.com`, or a VIDAA Store hostname appears in `tlsServerNames`, correlate it with the install window before deciding the next probe.
