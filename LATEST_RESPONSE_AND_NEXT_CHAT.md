# Sidee — prossimo test: Duplecast Install/Download

Data: 2026-09-26

## Obiettivo

Non stiamo più cercando di leggere il path HTTPS.

Il test nuovo serve a capire quali host VIDAA vengono:
- contattati specificamente durante Install/Download;
- ricontattati dopo il click;
- oppure compaiono per la prima volta solo nella fase install.

Target fisso:
- Duplecast
- App ID `1876`

## Modifiche implementate

Nuova card nel dashboard:

`Duplecast Install/Download Probe`

Nuovo report:

`storeInstallProbe`

Campi principali:
- `hostSnapshotAtInstallArm`
- `contactedAfterInstallArm`
- `newHostsAfterInstallArm`
- `queryDeltaAfterInstallArm`
- `dnsEvents`
- `phaseHosts`

Il traffico Store HTTPS resta diretto ai server VIDAA reali. Sidee osserva solo DNS.

## Test da fare

1. `git pull`
2. riavvia Sidee
3. lascia il DNS TV puntato al PC
4. apri il dashboard Sidee dal PC/telefono
5. premi **Start capture**
6. sulla TV apri lo Store e la scheda Duplecast
7. quando la scheda è visibile, premi **Detail page visible** sul dashboard
8. sul dashboard premi **Arm install capture**
9. subito dopo, sulla TV premi il normale **Install/Download**
10. quando lo Store ha restituito il suo risultato, premi **Finish capture**

Poi basta dire **fatto**.

Leggere:
- `reports/latest.json` su `sidee-reports`;
- prima `storeInstallProbe.newHostsAfterInstallArm`;
- poi `storeInstallProbe.contactedAfterInstallArm`;
- poi `storeInstallProbe.queryDeltaAfterInstallArm`;
- infine gli eventi `INSTALL_WINDOW`.

Questo test non modifica risposte Store, non intercetta TLS e non invoca install API da Sidee.
