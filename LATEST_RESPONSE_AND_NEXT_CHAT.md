# Sidee — Store loading failure after capture work

Data: 2026-09-29

Current symptom on TV:
- official App Store home opens;
- loading spinner remains;
- then “impossibile caricare contenuto”.

Latest report:
- session `sidee-20260929-160134-368c`;
- Store DNS traffic is active;
- repeated queries to `home-ui-eu`, `recommend-ui-eu`, `appstore-vidaa`, `detail-ui-eu` and other VIDAA hosts;
- no full-network capture is active in this report;
- Store subdomains are not being TLS-intercepted.

Potential Sidee interference found:
`config.json` still spoofed:
- `vidaahub.com`
- `www.vidaahub.com`

These root domains are no longer needed for the current Store work and could interfere with a Store/base service that resolves the root host directly.

Fix committed:
- remove `vidaahub.com` from spoof_domains;
- remove `www.vidaahub.com` from spoof_domains;
- keep only `vidaa.smartone-iptv.com` spoofed.

Next test:
1. git pull;
2. restart Sidee;
3. keep TV DNS pointed to the PC if desired;
4. close/reopen the official Store;
5. verify whether home/content loads normally.

If Store works again, root vidaahub spoof was the regression/interference.
If it still fails, inspect the next fresh report and then isolate DNS forwarding/network topology rather than Store TLS interception.
