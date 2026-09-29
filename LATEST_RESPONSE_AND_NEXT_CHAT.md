# Sidee — next test: verify capture topology before Store

Data: 2026-09-29

Latest Store install run:
- session `sidee-20260929-163507-4a6a`
- Duplecast was installed successfully
- `fullNetworkCapture` was missing from the synced report
- DNS Store timeline was present

Two separate causes identified:

1. Topology possibility:
If PC and TV are merely peers on the same hotspot/router, the PC cannot normally see TV -> Internet HTTPS unicast traffic. It may still see DNS packets addressed directly to the PC.

2. Reporting bug:
Full-network capture state was only synchronized into an already-existing Store report. With TV DNS automatic, a standalone pktmon capture could run without a report object and therefore never appear in GitHub.

Fix:
- ARM/CAPTURING/ERROR/STOPPED are now published;
- full capture creates its own report with accessMode `FULL_TV_NETWORK_CAPTURE` when necessary;
- pktmon status before stop is included in the summary.

Do NOT reinstall Duplecast yet.

Topology smoke test:
1. git pull
2. restart Sidee as Administrator
3. TV IP/DHCP automatic and DNS automatic
4. note current TV IPv4
5. enter TV IPv4 in Full Network Capture
6. press Arm / Start capture
7. on TV open YouTube and play a video for ~15-20 seconds
8. press Stop & analyze capture
9. say `fatto topology`

Interpretation:
- `FULL_PATH_VISIBLE` + HTTPS packet records > 0 => PC can see TV internet traffic; proceed to Store reinstall/download experiment.
- `DNS_OR_LOCAL_ONLY_LIKELY` or zero packet records => PC is not on the TV's gateway path; same-network pktmon cannot capture the install traffic.
