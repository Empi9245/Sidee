# Sidee — current network/capture test

Data: 2026-09-29

Current symptoms:
- phone connected to the shared/hotspot network has working Internet (~30 Mbps);
- TV on the same shared network cannot use YouTube/Store;
- therefore WAN quality is probably not the primary problem;
- strongest suspect: TV network settings, especially manual DNS and/or static gateway/subnet left from the old LAN.

For the FULL NETWORK CAPTURE phase:
- TV should use IP/DHCP AUTOMATIC;
- TV should use DNS AUTOMATIC;
- Sidee does NOT need to be the TV DNS server;
- enter the TV IPv4 manually in the Full Network Capture card.

Reason:
the manual TV-IP pktmon capture no longer depends on Sidee DNS. This removes Sidee DNS forwarding from the network path and gives a clean Internet baseline.

pktmon issue:
- user received: "pktmon already has active filters".
- Microsoft documents that `pktmon filter remove` removes ALL filters, not one named filter.
- Sidee was therefore intentionally refusing to remove them blindly.
- new behavior: if the only active filter is Sidee's own stale `Sidee-TV`, Sidee may stop a stale Sidee capture if active and safely clear the filter set;
- if any unrelated filter is present, Sidee still refuses to remove filters.

Next user test:
1. git pull
2. restart Sidee as Administrator
3. on TV set network/IP to automatic DHCP
4. set TV DNS to automatic
5. reconnect TV to the shared network
6. test YouTube FIRST
7. if YouTube works, note TV IPv4
8. enter that IPv4 in Sidee Full Network Capture
9. Arm / Start capture
10. Store -> Duplecast -> Install
11. Stop & analyze capture
12. report "fatto full capture"

If YouTube still does not work with IP+DNS automatic while phone works on the same shared network:
- problem is not Sidee DNS;
- inspect TV-assigned IP/gateway/subnet and Windows ICS/routing.
