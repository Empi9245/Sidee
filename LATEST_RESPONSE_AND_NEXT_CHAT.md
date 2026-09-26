# Sidee — stato aggiornato

Data: 2026-09-26

## Ultimo test passivo

Report:
- sessionId: `sidee-20260926-210157-6704`
- build: `app-8aaa5c0cb359`
- buildMatch: `true`
- 30 query DNS
- 20 host osservati

Sono ricomparsi:
- `layout-ui-eu.vidaahub.com`
- `appstore-vidaa.vidaahub.com`
- `tvmodules-vidaa.vidaahub.com`
- `home-ui-eu.vidaahub.com`
- `detail-ui-eu.vidaahub.com`
- `recommend-ui-eu.vidaahub.com`
- `partner.vidaahub.com`
- `vidaa-base-auth-eu.vidaahub.com`

`category-ui-eu.vidaahub.com` non è ricomparso in questa singola sessione, ma era stato osservato realmente nella sessione precedente; una mancata seconda query DNS può dipendere dalla cache.

## Priorità corretta

Core Store/UI:
1. `category-ui-eu.vidaahub.com`
2. `detail-ui-eu.vidaahub.com`
3. `layout-ui-eu.vidaahub.com`
4. `appstore-vidaa.vidaahub.com`

Secondari/supporto:
- `home-ui-eu`
- `recommend-ui-eu`
- `search-ui-eu`
- `partner.vidaahub.com`

`vidaa-base-auth-eu` resta interessante, ma riferimenti pubblici recenti lo associano anche a servizi base/OTA/update VIDAA, quindi non va considerato automaticamente un backend Store.

## Endpoint pubblicamente documentati su backend VIDAA moderni

Un progetto recente usa:
- `/api/v1.0.0/layoutApi/activityResources`
- `/api/v1.0.0/layoutApi/columnData`
- `/api/v1.0.0/detailApi/mediasInfo`

su host VIDAA dedicati a layout/detail.

Questo non prova ancora che la Q0707 Store usi gli stessi path, ma è il riferimento migliore per ricostruire la superficie API senza MITM.

## Prossimo passo

Non servono altri test TV immediati.

Continuare lato PC/repo:
- mappare solo endpoint read-only/publici;
- correlare `category-ui-eu`, `detail-ui-eu`, `layout-ui-eu`, `appstore-vidaa`;
- non riattivare lo spoof TLS Store;
- non usare credenziali/token/segreti provenienti da sorgenti pubbliche.
