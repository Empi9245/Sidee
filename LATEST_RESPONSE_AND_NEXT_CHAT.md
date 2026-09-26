# Sidee — stato aggiornato e prossimo test TV

Data: 2026-09-26

## Stato corrente

Il passive DNS discovery reale della Q0707 ha mostrato che il VIDAA Store usa host `vidaahub.com` diversi dal vecchio `category-ui`.

Per evitare test separati, Sidee ora traccia in pass-through questi host:

- `category-ui.vidaahub.com` — mantenuto come riferimento;
- `detail-ui-eu.vidaahub.com`;
- `appstore-vidaa.vidaahub.com`;
- `tvmodules-vidaa.vidaahub.com`.

Gli ultimi tre sono stati osservati realmente nel test TV precedente.

## Cosa è cambiato

- DNS spoof aggiunto per i tre host reali;
- nuovo certificato versionato `store-v2` con SAN per tutti gli host tracciati;
- TLS SNI observer multihost;
- proxy HTTPS verso lo stesso hostname richiesto dalla TV;
- Host header upstream coerente con l'host richiesto;
- response body restituito invariato;
- eventi/richieste/errori registrano anche l'host;
- `storeCatalogTrace.hostStats` mantiene uno stato separato per ogni host;
- `summary.storeTraceHosts` contiene la vista compatta host -> status;
- gli host tracciati non vengono più duplicati nel `storeDomainDiscovery` generico.

Gli status per-host restano:
- `IDLE`;
- `DNS_ONLY`;
- `TLS_SNI_ONLY`;
- `HTTP_PROXY_ACTIVE`;
- `REQUESTS_CAPTURED`;
- `PROXY_ERROR`.

La redaction precedente resta attiva: non vengono persistiti request headers/body, query values, Cookie/Authorization, token/session/signature o altri valori sensibili.

## Prossimo test

1. Sul PC fai `git pull`.
2. Chiudi eventuali vecchie istanze Sidee.
3. Riavvia Sidee.
4. Lascia il DNS della TV puntato al PC.
5. Apri il VIDAA Store ufficiale.
6. Naviga la home e almeno una categoria.
7. Apri una o più detail page reali.
8. Non serve fare altre azioni: attendi il normale sync del report.

Poi leggere `reports/latest.json` su `sidee-reports`.

Ordine di analisi:
1. `storeCatalogTrace.hostStats`;
2. `summary.storeTraceHosts`;
3. `storeCatalogTrace.events`;
4. `storeCatalogTrace.requests`;
5. per ogni HTTP response: host, method/path, query parameter names, status/content-type/length e JSON summary bounded.

La domanda da risolvere è:

> Quale tra detail-ui, appstore-vidaa e tvmodules-vidaa arriva realmente a TLS/HTTP sulla Q0707, e quali endpoint/path usa durante home, categoria e detail page?

Se un host resta `DNS_ONLY` o `TLS_SNI_ONLY`, non attribuirgli una funzione basandosi solo sul nome.
