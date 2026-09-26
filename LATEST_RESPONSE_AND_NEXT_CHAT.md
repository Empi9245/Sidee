# Sidee — test attuale: installazione Duplecast automatica

Data: 2026-09-26

Non servono più marker dalla TV o dal browser Sidee.

## Preparazione già fatta

- Store HTTPS resta diretto, senza MITM.
- `vidaa.duplecast.com` NON è più spoofato verso Sidee.
- Il dominio Duplecast reale viene risolto normalmente.
- Sidee avvia automaticamente la cattura quando vede il primo host Store/UI noto.
- Dopo l'avvio della cattura registra una timeline DNS bounded dello stesso client TV, compresi eventuali CDN esterni.
- L'IP TV serve solo in memoria per separare il client e non viene scritto nel report.

## Cosa deve fare l'utente

1. `git pull`
2. riavviare Sidee
3. lasciare DNS TV puntato al PC
4. aprire lo Store ufficiale sulla TV
5. cercare/aprire Duplecast
6. premere normalmente Install/Download
7. NON uscire dallo Store durante la prova
8. attendere il risultato dell'installazione
9. dire `fatto`

Non serve aprire Sidee nel browser della TV e non serve premere i marker manuali del dashboard.

## Cosa leggere dopo

`reports/latest.json`:

- `storeInstallProbe.status` dovrebbe essere `AUTO_CAPTURING`;
- `storeInstallProbe.triggerHost`;
- `storeInstallProbe.dnsEvents`;
- `storeInstallProbe.allDnsHosts`;
- `storeInstallProbe.allDnsQueryCount`;
- `storeInstallProbe.targetDomainHit`;
- `storeInstallProbe.targetDomainFirstSeenAt`;
- `storeDomainDiscovery`.

Ordinare mentalmente gli host per `firstSeenIndex`: quelli comparsi verso la parte finale, in coincidenza con Install/Download, sono i candidati più interessanti per package/CDN/auth/install.
