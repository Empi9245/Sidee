# Sidee — stato aggiornato

Data: 2026-09-26

## Risultato del test multihost

Il test ha chiarito perché la detail page mostrava "impossibile caricare contenuto".

Report:
- sessionId: `sidee-20260926-203224-8ef2`;
- build: `app-c022f88e412f`;
- buildMatch: `true`.

Status:

- `category-ui.vidaahub.com` -> `IDLE`
- `detail-ui-eu.vidaahub.com` -> `TLS_SNI_ONLY`
- `appstore-vidaa.vidaahub.com` -> `TLS_SNI_ONLY`
- `tvmodules-vidaa.vidaahub.com` -> `TLS_SNI_ONLY`

Non è arrivata nessuna richiesta HTTP.

Questo significa che la TV raggiunge Sidee, invia SNI, ma interrompe il collegamento TLS prima dell'HTTP. Il certificato locale non viene accettato dal client Store.

## Correzione già applicata

Gli host Store sono stati rimossi da `config.json -> spoof_domains`.

Dopo pull + riavvio:
- il VIDAA Store torna a collegarsi direttamente ai server reali;
- Sidee non interrompe più TLS;
- gli host vengono comunque osservati dal discovery DNS passivo.

Il codice multihost rimane nella repo ma non è attivo di default.

È stato inoltre aggiunto al discovery passivo:

`app-appstore.hismarttv.com`

per verificare se la Q0707 lo usa in un flusso Store successivo.

## Nuova interpretazione

`tvmodules-vidaa.vidaahub.com` è pubblicamente usato per il file:

`/deviceapi/vidaatv.js`

quindi è più plausibile che serva script/API device VIDAA piuttosto che catalogo/detail.

`appstore-vidaa.vidaahub.com` è servito tramite CloudFront/S3 ed è chiaramente associato allo Store.

`detail-ui-eu.vidaahub.com` resta il candidato più direttamente associato alla detail UI, ma il path HTTP non è osservabile con il MITM locale perché TLS viene rifiutato.

## Prossimo passo

Non riattivare lo spoof HTTPS dei domini Store.

Continuare con:
1. DNS passivo;
2. ricerca di asset/script e riferimenti pubblici ai domini osservati;
3. analisi di eventuali nuovi host Store emersi nella Q0707;
4. ricostruzione degli endpoint da risorse pubbliche senza modificare il traffico della TV.

Per un nuovo test TV basta:
- `git pull`;
- riavviare Sidee;
- lasciare il DNS TV sul PC;
- aprire normalmente lo Store e una detail page.

Questa volta la pagina non dovrebbe essere bloccata da Sidee perché i domini Store non vengono più spoofati.
