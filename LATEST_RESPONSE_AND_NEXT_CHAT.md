# Sidee — risultato install Duplecast e prossimo controllo

Data: 2026-09-29

## Sessione install catturata

`sidee-20260929-145316-dec1`

Build match: true.

Il probe automatico ha funzionato e ha registrato la timeline DNS mentre veniva eseguito il flusso Store/Duplecast.

## Cosa abbiamo escluso

Questi host NON sono specifici dell'installazione perché comparivano già nelle sessioni Store passive precedenti:

- `appstore-vidaa.vidaahub.com`
- `partner.vidaahub.com`
- `detail-ui-eu.vidaahub.com`
- `layout-ui-eu.vidaahub.com`
- `home-ui-eu.vidaahub.com`
- `recommend-ui-eu.vidaahub.com`
- `search-ui-eu.vidaahub.com`
- `tvmodules-vidaa.vidaahub.com`

## Host nuovi nella sessione install

Tra gli host VIDAA non presenti nei baseline precedenti sono comparsi:

- `geo-bas-eu.vidaahub.com`
- `abtest-tv.vidaahub.com`
- `archive-mmb-eu.vidaahub.com`
- `upgrade-plc-tv-eu.vidaahub.com`
- `sttc-bas.vidaahub.com`
- `member-ui-eu.vidaahub.com`
- `file-dl.vidaahub.com`
- `policy-jrnl-eu.vidaahub.com`
- `ota-tv.vidaahub.com` più tardi

`file-dl.vidaahub.com` è interessante, ma è comparso molto presto e fonti pubbliche mostrano che viene usato anche per file VIDAA generici/e-manual. Non considerarlo ancora il package host.

`vidaa.duplecast.com` NON è stato risolto durante la cattura (`targetDomainHit=false`).

## Prossimo test

Serve un solo controllo A/B, senza installare:

1. riavvia Sidee per ottenere una nuova sessione;
2. lascia DNS TV -> PC;
3. apri Store ufficiale;
4. cerca Duplecast;
5. apri la stessa detail page;
6. NON premere Install/Download;
7. resta sulla detail per circa 60-90 secondi;
8. poi dì `fatto baseline`.

Non serve aprire Sidee sulla TV e non serve nessun marker.

Poi confrontare la nuova RUN_BASELINE con:
`sidee-20260929-145316-dec1` (RUN_INSTALL).

Obiettivo:
trovare host/ordine/query presenti soltanto durante la vera installazione. Questo è molto più affidabile del dedurre il download dal nome del dominio.
