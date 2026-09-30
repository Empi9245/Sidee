# Acquisizione mirata: script caricati fuori dai tag DOM

30 settembre 2026. Tutte le letture obbligatorie completate prima di modifiche
e test. Base Sidee `f64aafa727c6801370554daa92488b5682fc76b9`, main;
base Nuvio `1f1ad284a292c06b0ed6b045dd1e1f3177666d1b`, main.

## Lacuna e decisione

I collector storici esaminavano `document.scripts` e salvavano estratti. Non
registravano la cronologia `performance.getEntriesByType('resource')` degli
script. Un caricamento visibile in quella cronologia può non avere più un tag
DOM. Il collector nuovo cerca esclusivamente questa differenza di copertura,
senza inventare URL o caricare SDK per ottenere un contesto diverso.

[check-loaded-source-coverage.mjs](check-loaded-source-coverage.mjs) legge i
report locali senza eseguire funzioni catturate. Il
[risultato](loaded-source-coverage-20260930.json) conserva hash dei report e
corpi selezionati, lunghezze e limiti. Le copie non sono sessioni indipendenti.
I wrapper principali erano già salvati senza marker di clipping; la lunghezza
originale non è sempre registrata, quindi non è una certificazione di completezza
del firmware. `mapAppInfoFields` non è registrata come corpo completo: questa
lacuna non spiega il rifiuto AppConfig e non giustifica un altro tentativo V2.

Decisione dopo la raccolta: se emerge uno script già caricato e leggibile con
codice ulteriore di importazione/staging, leggere quel codice localmente e
verificare contratto, provenienza e normali controlli prima di proporre una
candidata propria. Se non emerge, o la lettura è negata/CORS, quel canale non
fornisce il bundle. Non chiamare nuovi servizi, dedurre permessi da nomi di
funzioni o presentare l'assenza di script come impossibilità universale.

## Implementazione

`sidee.py --bridge-source-check --check-port 8082` entra nel modulo separato
`bridge_source_check.py` prima di configurare i worker normali. Nessun avvio
DNS/TLS, cattura, Git sync, inventario app, FileRead, write o installazione.
Non cambiano `web/app.js`, gli SDK, config, hosts o il ricevitore post-Store.

La pagina `web/bridge-source-check.html` esegue solo al clic **Raccogli una volta**:

- tag script e resource timing della pagina corrente; non legge altre pagine
  o processi Store/sistema e non invoca API VIDAA, getter identity o namespace;
- GET dei soli URL di script realmente osservati: stessa origine oppure il
  noto host `tvmodules-vidaa.vidaahub.com`, con CORS ordinario, credenziali omesse,
  redirect vietati e timeout; non richiede direttamente un endpoint presunto;
- massimo 12 letture, 1 MiB per sorgente, 4 MiB complessivi, 64 riferimenti;
  sorgenti con URL privati o literal di credenziali vengono omesse;
- stati `COMPLETE`, `TRUNCATED`, `EMPTY`, `DENIED` per HTTP 401/403,
  `UNAVAILABLE` per CORS/rete/TLS/timeout, `OUT_OF_SCOPE`, omissione sensibile
  o limite. Nessuno script recuperato viene eseguito;
- una ricevuta per processo ricevitore. Un retry identico reinvia la stessa
  raccolta senza rieseguirla; una seconda raccolta differente riceve HTTP 409.

Il ricevitore conserva soltanto campi del contratto, applica ancora il filtro
dei literal sensibili e salva hash SHA256 delle sorgenti UTF8 decodificate e
del report. Non confondere questo hash con i byte compressi ricevuti in rete.
Build incorporata nell'URL dello script confrontata col manifest; manifest
con hash dei quattro file, Git HEAD e stato dirty del collector. Firmware Q0707
è un riferimento storico esplicito, non una nuova chiamata alla TV.
Origin effettiva, secure context, timestamp e user agent sono dichiarati dal
browser; non costituiscono attestazione dell'hardware. Receipt `/status` omette
i corpi sorgente. Report grezzi in `reports/bridge-source-*.json`, ignorati da Git;
nessun upload o push automatico.

## Contesto prioritario e blocco di accesso

Rimane prioritario vidaahub.com. Il ricevitore HTTP isolato è raggiungibile su
`192.168.1.5:8082`; risponde anche a richieste Host `vidaahub.com:8082` che arrivino
tramite un instradamento **già presente**. Non crea quell'instradamento e non
impersona origini tramite DNS/TLS. Il mapping hosts del PC a 192.168.1.8 resta
preservato e non dimostra quale resolver usi la TV.

URL per la singola azione fisica, se l'instradamento TV vidaahub esistente arriva
già a questo PC: `http://vidaahub.com:8082/bridge-source-check.html`, poi premere
**Raccogli una volta**. HTTP/porta 8082 differiscono dal precedente HTTPS/443:
non è un A/B dei permessi e non si attribuisce al solo hostname la stessa
iniezione SDK. Un eventuale report LAN rimane separato e non risponde da solo
alla domanda sul contesto vidaahub. Non chiedere un altro snapshot LAN sostitutivo.

Se il nome non raggiunge il ricevitore, il blocco specifico è **assenza di un
canale di caricamento della pagina corrente nel contesto vidaahub**. Sidee può
ricevere dati dalla pagina aperta, ma il processo attivo :8080 è il vecchio
ricevitore inventory, senza un canale di comando alla TV. Non può navigare il
Browser, inserire il collector nella pagina di un altro processo né aprire
autonomamente quel contesto. Non risolvere il blocco con origini/identità
privilegiate false, bypass TLS o caricamento indiscriminato di codice.

## Verifica e stato effettivo

Passati off-TV: fixture JavaScript con accesso ai globali nativi proibito,
resource timing assente/presente, deduplica, URL privati, CORS/403, limite e
troncamento, corpo sensibile omesso; test HTTP su loopback e directory temporanea
per isolamento endpoint, build stale, origine estranea, schema, hash, omissione
campi non previsti, singola ricevuta e retry. Parsing Python/JavaScript e diff.
Nessun report di fixture salvato nella directory reports reale.

Ricevitore nuovo verificato su LAN :8082: `/status` e HTML HTTP 200; richiesta
dal PC con Host vidaahub:8082 HTTP 200. Questo prova soltanto servizio/routing
HTTP del PC, non apertura della TV o sua risoluzione DNS. Listener :8080 PID
5676 preservato. Controllare il PID nuovo corrente e `/status` prima di intervenire.
Al completamento della preparazione: **receipt null**, nessun nuovo dato TV.

Il blocco installante già misurato resta `installApplication` e `fileWrite`
respinti false/503 AppConfig; la decisione è sotto il trasporto JavaScript.
Questo collector può trovare eventuale codice web mancante, non leggere quel
servizio nativo o concedere autorizzazioni. I due metodi registrano metadata/URL
senza trasferire Nuvio. Mancano ancora import proprio consentito e tutte le
cinque prove finali di vera app. Nessuna correzione installante promessa.

Nuvio: aggiunta solo la nota in VIDAA_STATUS.md. Installer/packager locali e
dist preservati, nessun build/ZIP/commit. Sidee da committare con percorsi
espliciti, escludendo control/request.json già in staging; nessun push.
