# Sidee — risposta aggiornata + prossima chat

Data: 2026-09-26

## Stato da cui partire

Repository: `Empi9245/Sidee`  
Branch: `main`

Il **VIDAA Store Catalog / Transport Trace** pass-through è implementato.

Commit principali della fase:
- `7d3bfbd5a6e342014c54e590b99d41b2b1f6009e` — trace Store iniziale;
- `e3b980a85f1dc49145184338d990e8e346b82ef4` — hardening pass-through;
- `ad7a5e0ff6e33ddde60768d85fb49086c6f61e16` — dedupe metadata catalogo;
- `6effa59708db28cbbb3e6b25827808f4902cef55` — eventi trasporto bounded + resultCode/route-category;
- `f3e40ef01dd63d36764de1973c5f0b23cd18811d` — redaction errori nel recorder;
- `149ba71e9d37bba8beceb06718054e001975ffca` — test aggiornati;
- `2d96de0dd00d2d289a4ad14d646a71cc82a3ba4e` — AI_CONTEXT aggiornato.

La prossima chat deve comunque controllare l'HEAD reale prima di fare qualsiasi modifica.

## Cosa fa adesso Sidee

Per `category-ui.vidaahub.com`:

- DNS spoof verso il PC Sidee;
- SAN dedicato nel certificato multihost versionato;
- osservazione TLS SNI;
- proxy HTTPS verso il vero `https://category-ui.vidaahub.com`;
- metodo/path/query/body inoltrati quando necessari;
- body upstream restituito invariato;
- nessuna tile custom;
- nessuna installazione;
- nessun fileWrite;
- nessuna chiamata HiUtils/OMI inventata.

`storeCatalogTrace.events` è bounded e usa:

- `DNS`;
- `TLS_SNI`;
- `HTTP_REQUEST`;
- `HTTP_RESPONSE`;
- `PROXY_ERROR`.

Il report conserva soltanto dati diagnostici ridotti:
- timestamp;
- host;
- method/path;
- soli nomi delle query parameter;
- status/content-type/response length;
- top-level JSON keys;
- `resultCode` se presente;
- nomi bounded delle chiavi route/category;
- metadata catalogo/app non sensibili.

Non vengono persistiti request headers/body, query values, Cookie/Authorization, token, session, nonce, key, password, credential, signature/certificate material. Gli header eventualmente necessari continuano a essere inoltrati all'upstream senza essere loggati.

## Ultimo report reale disponibile

L'ultimo `reports/latest.json` controllato su `sidee-reports` è ancora:

`sidee-20260926-182425-cbe7`

con build match true ma **senza `storeCatalogTrace`**, perché appartiene alla fase precedente.

Quindi non abbiamo ancora il risultato TV del nuovo trace Store.

# Test da fare adesso sulla TV

1. Sul PC fai pull di `main`.
2. Chiudi eventuali vecchie istanze Sidee e riavvia Sidee.
3. Imposta il DNS della TV sull'IP del PC Sidee.
4. **Non aprire Smartone o Duplecast.**
5. Dal launcher apri il **VIDAA Store ufficiale**.
6. Naviga almeno una categoria.
7. Apri la detail page di una app reale; meglio una già installata.
8. In questa fase **non premere Install**.
9. Torna pure indietro/naviga un'altra app se serve per produrre una seconda chiamata.
10. Attendi il normale sync del report su `sidee-reports`.

Non serve aprire `https://vidaahub.com` per questo test: il traffico che ci interessa deve essere generato dallo Store ufficiale.

## Come interpretare il report

- nessun `storeCatalogTrace` / nessun DNS → la Q0707 non ha usato `category-ui.vidaahub.com` nel flusso testato;
- `DNS_ONLY` → hostname richiesto ma nessun SNI visto;
- `TLS_SNI_ONLY` → il client arriva all'handshake ma probabilmente rifiuta il certificato prima dell'HTTP;
- `HTTP_PROXY_ACTIVE` → almeno una richiesta HTTP ha raggiunto il proxy;
- `REQUESTS_CAPTURED` → abbiamo endpoint reali Q0707 da seguire;
- `PROXY_ERROR` → prima risolvere il trasporto/upstream, senza cambiare payload.

Se compare `categoryFirstResult`, il PoC FuVIDAA è compatibile almeno a livello catalogo con questa generazione. Se compaiono endpoint diversi, ignorare il vecchio endpoint e seguire solo quelli realmente osservati.

# Prossima chat — obiettivo unico

Leggi il nuovo `reports/latest.json` su `sidee-reports` e analizza **solo `storeCatalogTrace`**.

Rispondi prima a:

> La Q0707 usa davvero `category-ui.vidaahub.com`, e quali endpoint vengono chiamati quando apro catalogo e detail page?

Per ogni chiamata utile confronta in ordine:
- evento DNS/SNI/HTTP;
- method + path;
- query parameter names;
- upstream status/content-type/length;
- topLevelKeys;
- resultCode;
- routeCategoryKeys;
- catalogApps / unifiedAppName / openMode / packaged / hasDetailPage.

Non fare ancora:
- injection Nuvio;
- modifica delle risposte Store;
- Install;
- AppInfo write;
- pkgmgr inventato;
- brute force HiUtils/OMI;
- ritorno ai vecchi test AppConfig/identity/HSPDK.

Se `REQUESTS_CAPTURED` conferma il backend, il passo successivo deve essere deciso esclusivamente dagli endpoint reali osservati.
