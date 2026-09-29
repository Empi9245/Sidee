# Sidee — PCAPNG works; one more re-analysis for NAT-aware ports/peers

Data: 2026-09-29

The saved Duplecast-install capture is now readable directly:
- 1,328 PCAP packet blocks
- 384 decoded IPv4 packets
- TLS SNI includes VIDAA Store hosts such as `appstore-vidaa.vidaahub.com` and `tvmodules-vidaa.vidaahub.com`
- TV capture filter was `192.168.137.158`

Why `tvMatchedPacketRecords=0`:
- pktmon selected the TV flow using the Sidee-TV filter;
- at the NIC/PCAP stage Windows ICS/NAT can already have translated the packet addresses;
- requiring the literal private TV IP in each decoded packet was therefore wrong.

Latest fix:
- `aaaee33db770b1acb38441ed84cd8962923aca95`: analyze ports and peers across the already TV-filtered packet set and classify NAT-visible traffic separately.
- `37938067eca05b4e848ff2976d9698f234e543d0`: regression test for the NAT case.

Current SNI does not contain `vidaa.duplecast.com` or `files.duplecast.com`. Do not over-interpret that: a previous install-window DNS trace did see both, while this run may have reused cached DNS/TLS state.

## Next action — no reinstall

1. `git pull`
2. restart Sidee as Administrator
3. click **Re-analyze latest capture** again
4. reply `fatto nat`

Then inspect:
- filterScopedPacketRecords
- httpsPacketRecords
- topPeers
- tlsServerNames
- topologyClassification

No new Duplecast install is required for this step.
