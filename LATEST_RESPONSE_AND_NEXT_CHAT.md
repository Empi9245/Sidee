# Sidee / Nuvio — passaggio di consegne corrente

Aggiornato: 30 settembre 2026, Europe/Rome. Questo documento prevale sui piani
storici in AI_CONTEXT.md. Prompt: [NEXT_CHAT_PROMPT.md](NEXT_CHAT_PROMPT.md).
Indagine completata: [vidaahub-context-20260930.md](research/vidaahub-context-20260930.md).

## Richiesta e risultato corrente

L'utente ha chiesto di svolgere il lavoro su Sidee e Nuvio, con priorità a
vidaahub.com: verificare cambiamenti del contesto supportato, API e autorizzazioni
rispetto alle vecchie procedure. Non sostituire questa indagine con localhost/LAN.
Sono stati letti integralmente tutti i documenti obbligatori prima di modificare
o verificare. Nessun AGENTS.md trovato nelle repo o negli antenati controllati.

La ricerca pubblica e il confronto offline sono completati e documentati.
Un fornitore distingue le vecchie generazioni da VIDAA 5+; il maintainer vidaa-edge
riferisce bridge accessibile da v9 senza DNS rewrite. Non è una nuova concessione
di scrittura. Su Q0707 vidaahub esponeva già install legacy/V2, ma internamente
fallivano con AppConfig 503 anche con callback 0. Due contesti nativi respingevano
la scrittura pur con identità presente. Non è documentato quale aggiornamento
firmware cambiò le regole; manca un A/B vecchio/nuovo firmware.

Nessuna specifica pubblica consultata documenta una nuova origine autorizzata
Q0707 o un importatore per una propria app. Un diverso dominio resta ipotesi.
Il codice pubblico TVOЁ registra un URL remoto e considera callback 0 successo;
non prova un package locale o permessi applicabili a Nuvio. L'issue vidaa-edge 30
è ancora aperta, ultimo aggiornamento 9 settembre; codice default branch ancora
al commit 94c3134 del 3 dicembre 2025. Rebranding HomeOS non prova cambiamenti API.
Fonti, date, hash e limiti nel documento research; non ripetere questa ricerca
identica senza nuovi elementi tecnici.

**Contaminazione da ricordare:** hosts PC contiene `192.168.1.8 vidaahub.com`.
È preesistente e preservato. Il timeout HTTPS ordinario non misura il sito pubblico.
Google Public DNS via HTTPS ha restituito NODATA per A/AAAA alla verifica del
30 settembre (Status 0, nessuna Answer, SOA). Non è NXDOMAIN, prova universale o
whitelist. Sottodomini regionali Store e radice hanno ruoli distinti. Non sono
stati impersonati domini né eseguita enumerazione di origini per acquisire privilegi.

## Obiettivo e vincoli

TV **Hisense 50E77NQ**, firmware `V0000.09.60A.Q0707`, VIDAA U09.60,
MTK9603, Odin/Chromium 111. Modello interno storico 50E70LEVS_0003.
Nuvio deve avere launcher, frecce/OK/Indietro senza cursore, persistenza dopo
riavvio reale, UI utilizzabile con PC/Sidee/server locale spenti, caricamento e
riproduzione di un contenuto autorizzato. **Tutti e cinque ancora non verificati.**
Internet per contenuti/account è ammesso; l'utente non vuole ospitare l'UI.
Package locale/sideload/contenitore devono soddisfare i criteri. Una UI gestita
da un fornitore è una strada distinta con dipendenza esterna esplicita.
Bookmark, fullscreen, cache o service worker non bastano.

Esclusi devkit, Superdesign, Media Station X, contatti/percorso partner VIDAA,
sostituzioni ingannevoli di pacchetti Store, bypass di firme/autenticazione/AppConfig.
MSX è presente nello Store secondo l'utente e rifiutato: non riproporlo.

## Repository e preservazione

- Sidee: `C:\Users\empi0\Desktop\Sidee`, Empi9245/Sidee, `main`.
  HEAD all'inizio di questa ricerca: `bdd2c2d91ae1fc1e3cec6186c9b20bc49bff4bca`.
  Commit corrente di ricerca successivo: ricavarlo da Git; non confonderlo con
  il commit di esecuzione dei report, che quei sei report non registrano.
- Modifica utente preesistente: **A control/request.json**, già in staging.
  Esclusa dai commit dell'agente, da preservare. Blob
  `aefa724c1725b1ef2178c79fdd8914745bb9065e`; SHA256
  `6d8cd6ec102dd17b4ebd110e443fe6a68d645eee663ed1ce05fc2749699fa9b4`.
  Tutti i flag false. Non resettare lo staging.
- Nuvio: `D:\nuvio\nuviotvsmart`, `main`, HEAD invariato
  `1f1ad284a292c06b0ed6b045dd1e1f3177666d1b`.
  Modifiche locali di questa sessione: `installer/index.html`,
  `scripts/package-vidaa.mjs`, nuovo `VIDAA_STATUS.md`. Nessun commit Nuvio,
  bundle/ZIP/build o nuova installazione; conservarle. Nessun fetch/pull/push.

## Artefatti e verifiche di questa sessione

- `research/compare-vidaa-contexts.py`: solo lettura locale, sei report reali;
  JSON riproducibile `research/vidaa-context-comparison-20260930.json`.
  Hash/build/timestamp selezionati, niente credenziali/identificatori nativi.
  Verifica passata: rigenerazione identica, cinque contesti storici con false/503,
  ultima lettura inventory senza asserzione di permessi. Campi assenti = non
  registrati. Build uguale non prova A/B di origine o identico contesto nativo.
- Installer Nuvio: callback 0 mostra registrazione non verificata e nessuna copia
  di file alla TV; presenza API e rimozione non sono più dichiarate riuscite.
  Packager: messaggi onesti di ZIP web, nessuna promessa VIDAA U5+; logica invariata.
- Verifica off-TV: sintassi packager e script installer in ambiente DOM/API fittizio
  per callback 0, errore 503, API assente, eccezione, rimozione — tutti passati.
  Formattazione dei due file sorgente verificata. Non è una verifica sul firmware.
  Port/launcher/telecomando/playback non provati.

## Risposta TV già ricevuta: non ripetere

`reports/post-store-20260930-120901-112525.json` e `reports/post-store-latest.json`,
locali ignorati da Git. Timestamp pagina `2026-09-30T12:09:05.471Z`; ricezione
`2026-09-30T12:09:01.111526+00:00` (14:09 Europe/Rome). Entrambe 4281 byte,
SHA256 `78b8bc5564464bc9d17b823b482d6b3d94cebfe7d22f31e094da21229841ab4f`.
Origine `http://192.168.1.5:8080`, secure false, nessun build ID/HEAD nel report.
Elenco app **UNAVAILABLE**, package **READ_OK**, 18 componenti di sistema;
tvbrowser type web, `9.6.0-r20260706x`, `APPS:pkgs/tv.vidaa.app.tvbrowser/`.
Non è inventario completo Store, non legge byte di app e non prova assenza di
risorse Duplecast/Nuvio. Metadati Duplecast del 26 settembre precedono l'operazione
Store del 29. Stato attuale delle risorse ancora inconclusivo.

Ricevitore isolato verificato: PID 5676, listener LAN `192.168.1.5:8080`, GET
`/status` 200 con stesso report. Non modificato; non ascolta su loopback.
Non avviare Sidee normale: la sua pagina storica può eseguire startup probe.
Default spoof_domains vuoto, Store capture auto-arm false. Hosts PC non ripulito.
HTTPS già risolto: 382 record dopo NAT, FILTERED_FLOW_VISIBLE_AFTER_NAT.
Non ripetere cattura, inventario, identità, AppInfo/HSPDK/pkgmgr/FileRead/Write.

## Prossimo fatto e test decisivi

La matrice aggiornata in VIDAA_FEASIBILITY.md/research confronta package/sideload,
contenitore persistente e UI del fornitore. Nessuna strada è oggi dimostrata
capace di tutti i requisiti, senza concludere impossibilità universale.

Serve un fatto tecnico nuovo: procedura pubblica autorizzata per una propria app
su Q0707, con formato, contesto e storage documentati; oppure distribuzione
Nuvio gestita da un fornitore realmente utilizzabile, valutata come strada distinta.
Una nuova specifica di contesto deve descrivere autorizzazione, non solo esporre API.
Con il prerequisito soddisfatto, preparare app minima con ID proprio/versione
riconoscibile, importare secondo la procedura, verificare launcher/D-pad e poi
riavvio reale con PC/Sidee/UI host spenti, UI e playback autorizzato.
Senza quel prerequisito non c'è un ulteriore tentativo TV giustificato nei vincoli;
un diverso URL o un altro test LAN non sostituisce la prova.

## Letture obbligatorie per proseguire

Leggere integralmente NEXT_CHAT_PROMPT.md, AI_CONTEXT.md, questo documento,
README.md, VIDAA_FEASIBILITY.md, research/post-store-result-20260930.md,
research/vidaahub-context-20260930.md e il confronto JSON; in Nuvio VIDAA_STATUS.md.
Ricontrollare branch/HEAD/locali e provenienza prima di azioni. Preservare il lavoro
locale e committare Sidee su main con percorsi espliciti, mai control/request.json.
