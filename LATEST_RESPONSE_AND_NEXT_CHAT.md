# Sidee — HTTPS flow confirmed; correlate TLS hosts to peer IPs

Data: 2026-09-29

Latest re-analysis succeeded:
- 1,328 PCAP packet blocks
- 384 decoded IPv4 packets
- 384 filter-scoped packets
- 382 HTTPS packets
- topology: `FILTERED_FLOW_VISIBLE_AFTER_NAT`

This proves the Windows ICS/pktmon path is now working for the TV's real Store HTTPS traffic.

Current TLS SNI includes multiple VIDAA Store hosts, including:
- appstore-vidaa.vidaahub.com
- tvmodules-vidaa.vidaahub.com
- rsc-mntz.vidaahub.com
- home-ui-eu.vidaahub.com
- static-ui.vidaahub.com
- search-ui-eu.vidaahub.com
- journal/reporting hosts

Current top remote HTTPS peer is `98.67.144.87` with 148 packets / 40,098 bytes, but the previous parser did not yet attach each SNI hostname to its specific peer/flow.

New changes on main:
- `b03c71d7b90a3a80f3a0556644f5d4ea7eebf071`: adds `tlsHostFlows` with hostname → peer IP → packets → bytes.
- `bd7703d73ab0bb17d71ef607d82fb82f5c2a313c`: regression test.
- `14f24cff52bc2dafed0d83ea99c75a6181e82825`: UI shows TLS host→peer correlations.

## Next action — no reinstall

1. `git pull`
2. restart Sidee as Administrator
3. click **Re-analyze latest capture**
4. reply `fatto flows`

Then inspect `tlsHostFlows` and identify which VIDAA endpoint carried the largest share of the install-window HTTPS traffic.
