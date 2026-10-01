# Sidee / Nuvio — passaggio di consegne corrente

## 1 ottobre: accesso HTTP TV acquisito, clic e HTTPS da distinguere

Avvio reale utente: DNS18896, HTTP2848/collection bridge-c2f2b35c1a30469fbcfdd197f5602847,
runtime HEAD1236315, receipt null. TV .1.10 chiede root e script con Host vidaahub
alle07:30:07Z; DNS9query/9send/0errori. Sono richieste HTTP TV, non prova JS/
raccolta. Utente riferisce salto a HTTPS al clic; codice/receiver non navigano
né restituiscono redirect, causa effettiva non determinata. Nessun listener443.
Cert locale vidaahub auto-firmato (25set-25ott2026), non catena pubblica fidata;
non attivare il vecchio server normale o impersonazione TLS del contesto VIDAA.

Corretti listener UI quando module shim esiste nel browser, currentScript null,
button type/preventDefault e fetch di controllo/upload senza redirect/credenziali.
Test JS VM (native access vietato), retry identico e redirect respinto passati;
2test HTTP receiver passati. Attivazione pagina/provenienza reale da verificare
in /status; preservare eventuale ricevuta. Nessuna nuova operazione TV/installante.

## Correzione DNS e prossimo tentativo dopo riavvio TV

IP TV .1.10 e DNS primario .1.5 confermati dall'utente. Corretto lan_dns:
errore nel registro non blocca più risposta; eventi ravvicinati non persi,
contatori distinti per massimo32 client target con esito send/rcode/answers.
Submitted non attesta ricezione TV. Tre test passati, anche registro bloccato
con UDP/TCP reali e burst/client separati. DNS attivo PID10028, SHA c61f8b01...d49231,
sole sonde PC AUDP/TCP e AAAA NODATA: 3query/3submitted/0errori. DNS20404 sostituito
dopo identità verificata; HTTP19752/post-Store9552/ICS6844 intatti.
Chiesto riavvio elettrico TV (staccare corrente30s), poi http://vidaahub.com/.
Leggere nuovi contatori .1.10, HTTP e receipt prima di concludere. Nessuna nuova
ricevuta TV, causa cache non ancora provata; nessun cambio firewall/router/IPv6.

## Ultimo errore confermato: risoluzione nome TV

TV .1.10 confermata dall'utente, errore «name not resolved». Prima della sonda PC
il DNS non registrava nuove richieste target dopo le 20:27 (targetQueries9);
verifica 20:50 locale. HTTP solo PC, receipt null. Resolver standard Windows,
forzato .1.5 senza hosts, verifica A .1.5 TTL30, AAAA nessun record senza errore,
marker TXT proprio conforme. Sonde PC nuove aggiornano status: distinguerle da TV.
Regole Private UDP53 permissive già presenti, nessun cambio effettuato.
Domanda DNS poi risolta dall'utente: .1.5; IP TV .1.10 confermato.
Problema prima di HTTP, non nuova prova AppConfig; cache/resolver TV ancora da
distinguere. Nessun riavvio dei processi o probe/installazione eseguiti stavolta.

## Riscontro HTTP aggiunto dopo il nuovo fallimento

Attivato collector PID19752, collection bridge-5194a818c1e14b96b7d4e5b858ce4465,
build bridge-6bbcea0ceaa98b5e, runtime HEAD339fa8e, collectorDirty false.
Solo vecchio receiver2312 sostituito dopo identità/listener/receipt null verificati.
DNS20404/:8080 PID9552/ICS6844 intatti. Root+script HTTP200 dal PC, accessi .1.5
registrati, receipt null. Chiesto tentativo TV con http://vidaahub.com/ esplicito;
nessuna prova TV nuova. Leggere accessi live, non confondere readiness con report.

Il DNS riceve A vidaahub da 192.168.1.10; IP TV poi confermato. Vecchio
collector PID2312 receipt null, dato insufficiente a stabilire se la pagina
fosse stata aperta. Ora il receiver conta passivamente connessioni, richieste e
percorsi propri, distinti per IP privato (massimo 32). Stato /status.httpAccess
e bridge-domain-http-status.json locale ignorato; niente query/body/cookie/TLS.
Test reale: GET script, query non conservata, connessione senza richiesta,
isolamento e ricevuta singola/riuso passati. Nessun nuovo test VIDAA o Nuvio.
Per lo stato operativo leggere /status/readiness, non i vecchi PID sotto.
Errore «name not resolved», IP .1.10 e DNS primario .1.5 ricevuti.
Tutte le indicazioni precedenti sotto sono cronologia superata ove incompatibile.

## Ultimo setup LAN, superate le indicazioni hotspot

TV sulla rete del router confermato dall'utente. Implementato lan_dns.py,
DNS specifico 192.168.1.5:53 UDP/TCP, clienti LAN .1.0/24. Solo vidaahub.com
diretto al PC; AAAA/HTTPS NODATA senza NXDOMAIN, altro DNS via router .1.1.
PID20404; collector PID2312 e post-Store PID9552 intatti. ICS PID6844 RUNNING,
nessun servizio fermato. Nessuna nuova regola firewall, vecchie Private UDP53
preservate. DNS locale e forwarding verificati; nessuna ricevuta TV ancora.
Launcher ora avvia/riusa DNS conforme e collector, senza stop globali o Store.
Azione TV: DNS primario 192.168.1.5, riaprire Browser, http://vidaahub.com,
Raccogli una volta. Stato reale in bridge-domain-readiness.json e /status.

Ultimo errore TV: «failed to load page name not resolved». Root collector ancora
HTTP200, receipt null. DNS ICS risponde su 192.168.137.1 con A 192.168.1.5;
query verso 192.168.1.5 non risponde correttamente. Per TV sull'hotspot il DNS
primario è .137.1, non l'IP Ethernet .1.5 del vecchio log; launcher lo indica.
Chiesta conferma della rete TV (hotspot/router), risposta non ancora ricevuta.
AAAA su ICS restituisce nome inesistente: dato distinto da A riuscito, non prova
del resolver effettivamente scelto dalla TV o della causa unica. Chiudere/riaprire
Browser dopo l'eventuale correzione DNS e aprire http://vidaahub.com. Nessun probe
native, inventario o capture. :80/:8080 e ICS preservati.

Ultimo aggiornamento: autorizzazione esplicita utente ricevuta («autorizzo il
ripristino»). Solo receiver post-Store :8080 ripristinato PID9552, status verificato,
hash del report intatto. Nessun inventario o snapshot nuovo. Collector :80 PID2312,
collectionId bridge-d424a584b261425db1be7176edd852fd e receipt null preservati;
ICS PID6844 intatto. Il blocco di approvazione descritto sotto è ora risolto.

Readiness finale verificata attraverso il BAT e secondo avvio: root HTTP 200,
PID 2312, collectionId bridge-d424a584b261425db1be7176edd852fd,
build bridge-2f188c3d729a2bc3, runtime HEAD 100d4b0, collectorDirty false,
receipt null. DNS ICS PID 6844 attivo. :8080 fermo: ripristino respinto da
auto-review per rischio di ripetere inventario già esaurito; richiesta specifica
di approvazione inviata, non riavviare senza risposta. :80 non dipende da :8080.
Report post-store-latest locale alle 18:20:10 Europe/Rome, 4281 byte, hash
0efd7bac0e62b3c19b46141e1844d0127d07d14c086ddc531cd5c30c2370d2ba;
non la copia precedente delle 14:09, non modificato né raccolto durante questo fix.

## Ultimo fix dell'avvio Windows

Il log utente viene dal launcher storico: chiusura globale sidee.py, vecchio
flusso Store, DNS UDP53 in conflitto con ICS. :80 e :8080 risultavano spenti
al controllo. Ora start-windows.bat entra soltanto nel collector HTTP/80,
senza stop, DNS, elevazione o cambi firewall. Riavvio su un receiver conforme
conserva ricevuta e processo; build diversa/servizio estraneo resta intatto e
produce errore preciso. Binding Windows esclusivo. Test HTTP passato includendo
riavvio dopo una ricevuta e rifiuto di build diversa senza perdere il report.
PID/provenienza operativi da /status e reports/bridge-domain-readiness.json;
i precedenti PID 14152/5676 sono storici dopo quell'avvio. Nessun nuovo inventario
o install TV. Il Browser deve aprire http://vidaahub.com e cliccare una volta.

## Stato più recente: accesso root predisposto su vidaahub.com

L'utente richiede esplicitamente di spostare il collector alla radice del dominio.
Eseguito: receiver isolato HTTP/80, root `/`, http://vidaahub.com/. Corretto con
backup soltanto hosts vidaahub da 192.168.1.8 a 192.168.1.5. Il resolver ICS
192.168.137.1 ora risponde A 192.168.1.5; GET dal PC tramite il nome HTTP 200
con la pagina collector e senza app.js. Non è ancora una ricevuta TV.
PID root 14152, collectionId bridge-14ce9d228c2846b9b5b9351dc88de973; collector
build invariata bridge-fd277d6df6e660cf, runtime HEAD 14bf729. Vecchio :8082 fermato
dopo verifica assenza dati, post-Store :8080 PID 5676 e Windows ICS preservati.
Controllare http://192.168.1.5/status e reports/bridge-source-latest.json. La
richiesta fisica ora è aprire http://vidaahub.com e premere Raccogli una volta.
Nessun HTTPS/certificato, native API, SDK execution o nuovo test installante.
Le sezioni seguenti sono precedenti, incluse quelle che ritirano l'accesso root.

## Ultimo esito e correzione dell'accesso

La TV non apre l'URL collector :8082; l'utente riferisce «impossibile» e chiede
se WeinzII non indichi soltanto vidaahub.com. Receiver ancora attivo, receipt
null, nessun report bridge-source-latest.json. Ritirata l'istruzione di apertura
non preceduta dalla verifica del canale TV → PC. Il solo nome vidaahub non
carica il collector locale, e HTTP/8082 non è la radice HTTP/HTTPS ordinaria.
Non ripetere quell'URL né proporre la radice pubblica come acquisizione già
preparata. Non attribuire l'errore a DNS o AppConfig senza evidenza aggiuntiva.
Vedi research/bridge-source-acquisition-20260930.md, aggiornamento finale.

Aggiornato: 30 settembre 2026, Europe/Rome. Questo documento prevale sui piani
storici in AI_CONTEXT.md. Prompt: [NEXT_CHAT_PROMPT.md](NEXT_CHAT_PROMPT.md).
Indagine completata: [vidaahub-context-20260930.md](research/vidaahub-context-20260930.md).

## Stato corrente: acquisizione mirata implementata, ricevuta TV assente

[Protocollo e blocco tecnico](research/bridge-source-acquisition-20260930.md).
Creati bridge_source_check.py e web/bridge-source-check.js/html; nuova modalità
isolata `sidee.py --bridge-source-check --check-port 8082`. La lacuna concreta
è resource timing degli script già caricati, non registrato dal precedente
collector di document.scripts. Nessuna scansione native namespace o chiamata
TV, SDK caricato/eseguito, filesystem, vecchio inventario, capture o write.
Hash/provenienza/completezza e singola ricevuta locale, niente Git upload.

Verifiche JS e HTTP off-TV passate. Receiver pronto su 192.168.1.5:8082,
HTML/status 200 e Host vidaahub:8082 accettato dal PC; **receipt null**.
Questa non è una prova TV/routing DNS TV. :8080 PID 5676 preservato.
Prima di continuare controllare `/status`; usare immediatamente eventuali
reports/bridge-source-latest.json e history, ignorati da Git. Non ripetere una
raccolta ricevuta e non interpretare user agent come attestazione del dispositivo.

Priorità vidaahub: URL http://vidaahub.com:8082/bridge-source-check.html solo
tramite instradamento già presente, poi clic Raccogli una volta. Non creati
DNS/TLS per quel nome. HTTP/8082 differisce da HTTPS/443; non è test permessi.
Se la TV non può caricarlo, manca quel canale di caricamento, non il consenso.
Sidee non può aprire/navigare il Browser o inserire il collector in altri processi.
Il nuovo dato potrebbe recuperare un bundle già caricato ma assente dai vecchi
estratti; non può fornire l'implementazione nativa AppConfig dietro il 503.
Nessuna candidata installante o criterio finale Nuvio verificato.

Nuvio: aggiornato solo VIDAA_STATUS.md; installer/packager locali preservati,
nessun build/ZIP/commit. Sidee base f64aafa727c6801370554daa92488b5682fc76b9;
HEAD finale da Git. control/request.json resta staged invariato ed escluso dal
commit su main, senza push. Le sezioni seguenti documentano fasi precedenti.

## Richiesta corrente: consegna per soluzione o acquisizione TV tramite Sidee

L'utente ha chiesto un prompt per la prossima chat: deve trovare una soluzione
oppure modificare Sidee per acquisire dalla sua TV i dati che servono a trovarla.
Il compito operativo è ora esplicito in NEXT_CHAT_PROMPT.md: identificare una
lacuna concreta, verificare i dati già disponibili, implementare una raccolta
mirata se fattibile, acquisire una ricevuta reale e usare subito il risultato.
Non basta ripetere che manca il codice nativo o proporre altre ricerche online.

I test sulla propria TV sono già autorizzati. L'acquisizione deve restare entro
osservazioni/letture consentite e gestire i dinieghi; i vincoli contro bypass,
impersonazione e sostituzioni ingannevoli restano. Una necessaria azione fisica
va chiesta precisamente dopo aver preparato collector e ricevitore. Non esiste
ancora un nuovo collector per questa lacuna: questa consegna è solo documentale,
nessun nuovo test TV, server, build Nuvio o risultato di installazione.

Sidee main prima della consegna: 513f85ea8646ba0628699781cd3d446fb94afca7.
Staging e hash di control/request.json ricontrollati e invariati; file escluso
anche dal commit documentale. HEAD finale della consegna da leggere in Git.

## Ultima richiesta: studiare il codice VIDAA locale, senza ricerca online

L'utente conferma hisense://debug **già provato**: non riproporlo. Non ha dato
un esito tecnico puntuale, quindi non attribuire un errore specifico alla TV.
Le domande UI precedenti sono superate per questa fase. Il
[controllo alternative](research/alternative-install-check-20260930.md) è storico.

Scanditi 65 report JSON locali per sorgenti/excerpt; letti integralmente i wrapper
store e service selezionati. Analisi aggiornata in
[install-methods-q0707-20260930.md](research/install-methods-q0707-20260930.md).
Nuovo riscontro verificato: return true nel ramo package è anticipato; dopo
package riuscito il wrapper chiama comunque Hisense_installApp e può dare un
callback package positivo anche se il launcher fallisce. Non è una nuova prova
di installazione package TV o di applicabilità del 503 a ogni suo payload.

[Audit offline](research/audit-vidaa-install-contract.mjs),
[risultato](research/vidaa-install-contract-20260930.json): due corpi originali
vincolati all'hash del report, VM con trasporto fittizio, quattro scenari passati.
Zero rete/TV, nessun altro sorgente eseguito, argomenti/identità non esportati.
Il materiale locale non contiene l'implementazione del servizio nativo che applica
AppConfig né uno stager/schema d'import Nuvio verificato. Limite dei dati, non
prova di impossibilità universale. Nessuna soluzione installante individuata.

## Ultima richiesta: risolvere V2 o trovare un'alternativa

[Diagnosi dei tre percorsi](research/install-methods-q0707-20260930.md).
Il metodo upstream New (File System) è diverso da Hisense_installApp_V2.
Le sorgenti catturate dalla TV il 25 settembre mostrano legacy/V2 che convergono
sullo stesso helper e backend installApplication. In entrambi i tentativi:
fileRead true/0, poi installApplication false/503 AppConfig (SDK 1.5.0), callback
0 e return false. Non fallisce il controllo di tipo oggetto V2; non è però provata
la validità di ogni altro campo dopo un eventuale permesso. New usa una scrittura
diretta già respinta nel no-op vidaahub del 26; non ripetuta la routine upstream.

Confronto offline aggiornato con operazioni backend e hash delle tre sorgenti,
senza argomenti/registro/identità; rigenerazione e riscontri sui report verificati.
Nessuna nuova chiamata TV o correzione installante. Tutti i criteri finali ancora
non verificati. Un importatore/contenitore normale resta alternativa da trovare,
non soluzione promessa. Sidee non è un telecomando generale e non può aprire
autonomamente i menu TV: manca un canale per quell'osservazione, non il consenso
ai test. L'autorizzazione dell'utente persiste.

## Ultima correzione: il meccanismo vidaa-edge

L'utente ha indicato https://github.com/weinzii/vidaa-edge e chiarito perché il
contesto vidaahub conta. Riletti README, template/componente installer e servizio
app alla revisione 94c3134911cbd4b813eea1f88c56819c0981518b.
[Analisi del codice e correzione](research/vidaa-edge-context-review-20260930.md).

L'indicazione dell'assistente di aprire il sito pubblico con DNS automatico era
sbagliata per verificare quel meccanismo: il progetto usa quel contesto per
esporre le API alla pagina del toolkit. Le richieste DNS automatico/E-Manual
sono ritirate. Non riproporre il test LAN come risposta alla domanda vidaahub.
La raggiungibilità Internet della radice non decide il funzionamento descritto.

Il servizio upstream verifica presenza delle funzioni, registra URL via legacy
oppure modifica registro app via HiUtils. Non trasferisce il bundle Nuvio; il
ramo legacy tratta callback 0 come successo. I report Q0707 nel contesto vidaahub
avevano già le API ma false/AppConfig 503 internamente. Il codice corrente non
identifica un nuovo metodo autorizzato che renda quelle operazioni accettate.
Non concludere impossibilità universale; non progettare bypass dei rifiuti.

L'utente autorizza prove dirette anche prima di documentazione pubblica. Era
stato preparato un test UI/telecomando Nuvio su :8181; ora **fermato**, solo il
nostro PID 3712, nessun report TV ricevuto. Codice e fixtures conservati in
nuvio_tv_check.py/web/nuvio-tv-check.js, protocollo storico in
research/tv-acceptance-20260930.md. Non è la candidata di installazione corrente.
Ricevitore post-Store PID 5676 preservato; UDP 53 preesistente PID 6844 è Windows
SharedAccess/ICS, non modificato. Nessun nuovo DNS/TLS/install/probe/cattura.

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

## Prossimo lavoro e test decisivi

Scegliere una lacuna tecnica che possa cambiare la decisione sull'importazione
di una propria app Q0707; controllare prima report e sorgenti già disponibili.
Esempi pertinenti, se realmente mancanti e accessibili: sorgenti complete già
caricate, contratto di uno stager/importatore consentito, diagnostica del rifiuto,
prova delle risorse conservate di una app propria. Non sono endpoint presunti
né un'autorizzazione a scandire storage o raccogliere identità/credenziali.

Se manca un dato acquisibile, modificare Sidee con modalità isolata e raccolta
singola esplicita, limitata a quel dato, con build/commit, origine, timestamp,
hash e stato di completezza. Conservare dinieghi e assenze come tali. Verificare
il collector e acquisire dalla TV con un canale disponibile; se un passaggio
fisico è inevitabile, preparare tutto e chiedere soltanto quell'azione precisa.
Non avviare i vecchi auto-probe, non ripetere inventario/HTTPS/debug/LAN UI.

Usare il risultato per costruire una candidata consentita. Un importatore
concreto richiede prima app minima propria e poi verifica distinta di package,
launcher, telecomando, riavvio reale con host spenti, UI e contenuto autorizzato.
Nessuna strada è oggi dimostrata capace di tutti i requisiti. Se la raccolta non
è fattibile, descrivere il limite specifico del canale e il dato ancora necessario;
non inventare un'installazione o una impossibilità universale. Il prompt corrente
contiene il dettaglio operativo e la distinzione fra API, permessi e risorse.

## Letture obbligatorie per proseguire

Leggere integralmente NEXT_CHAT_PROMPT.md, AI_CONTEXT.md, questo documento,
README.md, VIDAA_FEASIBILITY.md, research/post-store-result-20260930.md,
research/vidaahub-context-20260930.md e il confronto JSON; in Nuvio VIDAA_STATUS.md.
Leggere anche research/install-methods-q0707-20260930.md per non confondere i metodi.
Leggere research/alternative-install-check-20260930.md come storico; debug già provato.
Ricontrollare branch/HEAD/locali e provenienza prima di azioni. Preservare il lavoro
locale e committare Sidee su main con percorsi espliciti, mai control/request.json.
