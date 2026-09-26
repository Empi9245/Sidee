# Sidee — stato aggiornato

Data: 2026-09-26

## Ultimo test reale

Dopo il fallback alla modalità passiva, la Q0707 ha prodotto:

- sessionId: `sidee-20260926-204550-b8a4`
- build: `app-4ce89e866abf`
- `QUERIES_CAPTURED`
- 42 query DNS
- 23 host VIDAA osservati

Il risultato più importante è:

`category-ui-eu.vidaahub.com`

Il precedente PoC FuVIDAA usava la famiglia `category-ui.vidaahub.com`; sulla TV europea corrente è comparsa invece la variante regionale `category-ui-eu`.

Altri host funzionali osservati:
- `layout-ui-eu.vidaahub.com`
- `detail-ui-eu.vidaahub.com`
- `search-ui-eu.vidaahub.com`
- `home-ui-eu.vidaahub.com`
- `recommend-ui-eu.vidaahub.com`
- `appstore-vidaa.vidaahub.com`
- `tvmodules-vidaa.vidaahub.com`
- `vidaa-base-auth-eu.vidaahub.com`
- `partner.vidaahub.com`

## Stato tecnico

NON riattivare lo spoof HTTPS Store: la Q0707 rifiuta il certificato locale prima dell'HTTP.

`category-ui-eu.vidaahub.com` è stato aggiunto agli host noti del trace per completezza, ma non è presente in `spoof_domains`: resta quindi passivo di default.

## Evidenza pubblica utile

Un progetto recente, `kineticman/FastChannels`, usa backend VIDAA moderni con:
- famiglia `layoutApi`;
- famiglia `detailApi`;
- endpoint `/api/v1.0.0/detailApi/mediasInfo`;
- host VIDAA partner dedicati a layout/detail;
- `partner.vidaahub.com` nel flusso di autenticazione.

Questo è coerente con gli host `layout-ui-eu`, `detail-ui-eu` e `partner.vidaahub.com` osservati sulla Q0707, ma non prova che i path siano identici nel VIDAA Store TV.

## Prossima direzione

Continuare senza MITM:
1. mappare riferimenti pubblici/asset per `category-ui-eu`, `layout-ui-eu`, `detail-ui-eu`;
2. confrontare con i path pubblicamente documentati delle famiglie `categoryApi`, `layoutApi`, `detailApi`;
3. usare solo richieste read-only e senza credenziali della TV;
4. non tornare ai vecchi test install/AppInfo/HSPDK finché la superficie Store moderna non è mappata meglio.
