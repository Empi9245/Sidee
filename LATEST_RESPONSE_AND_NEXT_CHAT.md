# Sidee — Store spinner: DNS fast-path fix

Data: 2026-09-29

Symptom persisted after removing root vidaahub spoof:
- Store home partially loads;
- spinner;
- "impossibile caricare contenuto".

Fresh session:
`sidee-20260929-161057-217e`

Observed pattern:
- repeated A lookups every few seconds to `home-ui-eu`, `appstore-vidaa`, `img`, `rsc-mntz`;
- no Store TLS interception;
- spoof list only contains `vidaa.smartone-iptv.com`.

Root cause candidate found in Sidee:
the DNS loop performed synchronous diagnostic/report writes BEFORE forwarding/replying to the TV. The automatic Store timeline can write a growing JSON report on every DNS query. The DNS resolver was also single-threaded, so one slow upstream lookup blocked the rest.

Fixes:
1. DNS fast path:
   receive -> resolve/spoof -> send response -> queue diagnostics.
2. Diagnostic Store/DNS logging now runs in a background queue worker.
3. DNS requests are concurrent with a bounded 32-request semaphore.
4. UDP receive buffer raised to 65535.
5. DNS TCP fallback is used when an upstream UDP reply has TC/truncated set.
6. New GET endpoint:
   `/api/dns-health`
   exposing counts/latency/failures/queue depth/worker peak.

Next test:
1. git pull
2. restart Sidee
3. TV DNS stays pointed to PC
4. reopen official Store
5. report whether content now loads.

If it still fails:
- read `http://<PC-IP>:8080/api/dns-health` or use report/log;
- temporarily set TV DNS to automatic/router once as a clean A/B test.
If Store works on automatic DNS but not Sidee DNS, resolver forwarding remains the issue.
If Store fails even on automatic DNS, the problem is outside Sidee DNS and should be isolated from TV/router/cache/network state.
