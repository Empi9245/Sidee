# Prompt per la prossima chat — 30 settembre 2026

## Stato corrente: IP e DNS confermati, correzione DNS attiva

Utente conferma TV .1.10 e DNS primario .1.5: non richiederli di nuovo.
Ultimo errore resta «name not resolved». Individuato nel codice lan_dns un
errore di robustezza: OSError salvando il registro interrompeva anche la risposta.
Corretto e verificato con file bloccato su UDP/TCP reali; non attribuire senza
prova a questo difetto il fallimento precedente. Rimossa perdita dell'ultimo
evento dei burst dovuta al throttle di un secondo. Ora status conserva massimo
32 client del solo target, richieste e risposte submitted/error, tipo, trasporto,
rcode e numero risposte. Submitted significa send del socket, NON ricevuta TV.
Nessun altro nome/query/body/cookie/capture/SDK/native conservato o eseguito.
Solo DNS20404 sostituito dopo marker/hash, executable/cmdline e ownership bind
verificati; backup status precedente locale ignorato. Nuovo DNS PID10028,
SHA256 c61f8b01b713153a9ddf8781ce2429fbbca942da6e6be1b6aa97b32689d49231.
Collector19752, post-Store9552 e ICS6844 intatti. Tre test DNS passati, resolver
Windows A .1.5 UDP/TCP e AAAA NODATA; launcher --background riusa il server.
Primi contatori soltanto PC: tre richieste/tre submitted/zero errori; niente TV.
Chiesto riavvio elettrico TV (corrente staccata30s) e http://vidaahub.com/ per
ottenere un tentativo dopo riavvio del resolver. Leggere subito clients['.1.10']
in reports/bridge-domain-dns-status.json, accessi HTTP e receipt. Non assumere
cache come causa provata. Nessuna nuova regola firewall o modifica router/IPv6.
I paragrafi sotto sono cronologia superata dove incompatibili con questo stato.

## Ultimo dato TV: «name not resolved», IP .1.10 confermato

L'utente conferma IP TV 192.168.1.10. Prima della nuova sonda PC, DNS fermo
al targetQueries9/client .1.10/timestamp 2026-09-30T18:27:33Z (20:27 locale),
mentre verifica 20:50:12 locale: nessuna nuova richiesta target registrata per
l'ultimo fallimento. HTTP collector PID19752 vede soltanto PC .1.5, receipt null.
Verifica Windows Resolve-DnsName esplicita a .1.5, DnsOnly/NoHostsFile:
A vidaahub → .1.5 TTL30; AAAA nessun record senza errore; TXT marker del proprio
server corrisponde al SHA lan_dns d0616fe...ee961. Sonde PC successive aggiornano
il lastTargetClient .1.5: non scambiarle per TV. Processo/bind DNS20404 confermati;
regole Sidee Private UDP53 Allow hanno Local/Remote/Program Any, sola lettura.
Il blocco osservato è prima del caricamento HTTP: DNS effettivo/cache Browser
TV o percorso di risoluzione restano da distinguere, non un nuovo rifiuto AppConfig.
Domanda DNS poi risolta: valore .1.5 confermato, come IP TV .1.10.
Non ripetere la domanda IP né il tentativo identico senza cambiare/verificare
quel prerequisito. Nessuna modifica router/IPv6/DoH/firewall o nuovo probe TV.

## Stato più recente: distinguere DNS e accesso HTTP locale

Riscontro ATTIVO: collector :80 PID19752, collectionId
bridge-5194a818c1e14b96b7d4e5b858ce4465, build bridge-6bbcea0ceaa98b5e,
runtime HEAD 339fa8e670348ddf12de04ade073dfb22bfe53da, collectorDirty false.
Sostituito soltanto il vecchio PID2312 dopo verifica identità/listener/receipt null;
DNS20404, post-Store9552 e ICS6844 intatti. Root e JS HTTP200 dal PC; accessi
registrati solo da .1.5 alla verifica, non prova per i tentativi TV precedenti.
Receipt ancora null. Chiesto un tentativo con http://vidaahub.com/ esplicito
dopo la riapertura del Browser. Controllare subito /status e gli accessi live;
readiness è una fotografia PC, non un report TV. Niente nuove regole firewall.

Dopo «non funziona ancora», DNS LAN PID20404 registra richieste A vidaahub da
192.168.1.10 (8 al controllo); IP poi confermato dalla TV dall'utente.
Non dire che il DNS sia rimasto irraggiungibile o che una query provi il GET.
Collector precedente PID2312 aveva receipt null e nessun contatore accessi;
receipt null da solo NON prova assenza di apertura pagina.
Implementato riscontro passivo del solo receiver HTTP: connessioni TCP accettate,
richieste GET/POST e conteggi per sei percorsi noti; altri percorsi/Host mascherati.
Solo IP privati, massimo 32 client; niente query, body, cookie o cattura TLS.
Stato in /status.httpAccess e reports/bridge-domain-http-status.json ignorato.
Errore di scrittura diagnostica non blocca il servizio. Test HTTP reale passato,
inclusa connessione senza richiesta e query sensibile non conservata.
Leggere /status per provenienza effettiva dopo l'attivazione; conservare qualsiasi
ricevuta prima di cambiare un processo. DNS e :8080 non richiedono riavvio.
Errore «name not resolved», IP .1.10 e DNS primario .1.5 confermati.
I paragrafi sotto sono cronologia: prevale questo stato e il runtime verificato.

## Ultima correzione: TV sulla LAN router, DNS dedicato al PC

L'utente conferma: NON usa hotspot, TV sulla rete router. Le istruzioni .137.1
sotto sono ritirate per questo collegamento. Ora lan_dns.py serve il DNS isolato
UDP/TCP **192.168.1.5:53**, solo clienti 192.168.1.0/24: vidaahub.com A .1.5,
AAAA/HTTPS NOERROR/NODATA, altre query inoltrate a router .1.1. Nessun capture,
probe SDK/native, altri hostname riscritti o log delle query ordinarie.
Binding esclusivo specifico LAN possibile senza fermare ICS, servizio PID6844
ancora RUNNING. DNS PID20404, collector :80 PID2312 e post-Store :8080 PID9552
preservati. Query A UDP/TCP, NOERROR AAAA/HTTPS e forwarding ordinario verificati
dal PC fuori dalle restrizioni di rete della sonda iniziale; non sono prove TV.
start-windows.bat avvia/riusa anche DNS LAN prima del collector, abortisce se
non ne verifica marker/hash e i due trasporti. Regole esistenti Private UDP53
preservate; nessuna nuova regola (UAC di un helper opzionale annullata, helper
ritirato). Collector corrente stessa collectionId, receipt null alla verifica.
TV: DNS primario 192.168.1.5, chiudere/riaprire Browser, http://vidaahub.com,
Raccogli una volta. Leggere subito /status e report se arriva. Non cambiare
router/DoH/IPv6, fermare ICS o ripetere inventario/capture/write gate.

ULTIMO ESITO: TV «failed to load page name not resolved», non raccolta eseguita.
Collector :80 PID2312 attivo, /status tramite dominio HTTP200 e receipt null.
ICS 192.168.137.1 risponde A vidaahub.com → 192.168.1.5; query DNS allo stesso
IP Ethernet 192.168.1.5 fallisce (connessione interrotta). Query AAAA su ICS
riporta nome inesistente; non dedurre che anche A sia assente. Il setting/resolver
effettivo della TV non è ancora letto. ARP hotspot contiene .137.158 storico TV,
non attestazione. Domanda specifica inviata: hotspot PC oppure rete router?
Per TV sull'hotspot usare DNS primario 192.168.137.1, chiudere/riaprire Browser,
poi http://vidaahub.com. Non indicare .1.5 come DNS di ICS. Launcher aggiornato
con questo dato specifico della configurazione corrente. Non cambiare servizi,
IPv6, gateway o connessione TV alla cieca; se il problema persiste con quel DNS
confermato, va distinto il negativo AAAA dalla cache/resolver della TV.

ULTIMO STATO: l'utente ha risposto «autorizzo il ripristino». Ripristinato soltanto
receiver post-Store :8080 PID9552, /status mode post-store-check; hash del report
0efd7bac0e62b3c19b46141e1844d0127d07d14c086ddc531cd5c30c2370d2ba invariato.
Nessuna pagina post-Store aperta sulla TV o nuova raccolta. Collector :80 PID2312
e collectionId bridge-d424a584b261425db1be7176edd852fd preservati, receipt null;
ICS UDP53 PID6844 intatto. La richiesta di approvazione pendente sotto è risolta.

Stato operativo finale del fix launcher: avvio reale del BAT verificato,
receiver 192.168.1.5:80 PID 2312, collectionId
bridge-d424a584b261425db1be7176edd852fd, build bridge-2f188c3d729a2bc3,
runtime HEAD 100d4b0e2f6c00a1df38e070dc4865b755f17c05, collectorDirty false.
Secondo avvio BAT verificato: stesso PID/collectionId, nessun DNS/stop.
Root via dominio HTTP 200, receipt null. ICS UDP53 PID 6844 resta attivo.
:8080 ora fermo: auto-review ha respinto il ripristino del ricevitore storico
per rischio di ripetere inventario esaurito; domanda specifica inviata all'utente.
Non riavviarlo senza risposta/autorizzazione. Il collector :80 è indipendente.
post-store-latest presente di una ricezione precedente alle 18:20:10 Europe/Rome,
4281 byte SHA256 0efd7bac0e62b3c19b46141e1844d0127d07d14c086ddc531cd5c30c2370d2ba,
diverso dalla copia 14:09 sotto; file intatto, non una raccolta lanciata ora.

## Ultimo fix: launcher Windows isolato, nessun DNS o stop globale

L'utente ha aperto start-windows.bat, ancora storico: fermava indistintamente
tutti i processi sidee.py, poi avviava il flusso Store e DNS su UDP53 già ICS.
Dopo il log, i listener :80 e :8080 erano assenti. Corretto start-windows.bat:
solo --bridge-source-check --check-port 80, senza elevazione, firewall, Git sync,
DNS o arresto processi. Il receiver riusa un processo attivo solo se mode e
hash dei quattro sorgenti corrispondono; non azzera la ricevuta o uccide un
servizio diverso. Binding Windows esclusivo per impedire due receiver sulla
stessa porta. Test HTTP off-TV passato per riavvio con ricevuta e build diversa.
Per PID/collectionId/HEAD correnti leggere /status e reports/bridge-domain-readiness.json,
non riutilizzare gli ID storici sotto. Riavvio operativo e verifica attraverso
il launcher corretti prima della consegna; nessuna nuova raccolta TV dichiarata.
Non fermare Windows ICS UDP53. Azione TV: http://vidaahub.com → Raccogli una volta.

## Ultima correzione operativa: collector alla radice vidaahub

La richiesta successiva esplicita dell'utente è predisporre il collector perché
la TV apra soltanto vidaahub.com. Supera il precedente ritiro dell'URL e il
vincolo di non correggere l'instradamento locale: nessun bypass o probe nativo.
Receiver isolato spostato su HTTP/80, radice `/`: **http://vidaahub.com/**.
Il DNS ICS 192.168.137.1 restituiva il vecchio IP 192.168.1.8; dopo la sola
correzione della riga hosts restituisce 192.168.1.5. Backup byte per byte locale
ignorato da Git. Collector/root HTTP 200 verificati dal PC tramite il nome;
non dichiarare apertura TV finché non arriva la ricevuta. Processo :80 PID 14152,
collectionId bridge-14ce9d228c2846b9b5b9351dc88de973, build bridge-fd277d6df6e660cf,
Git HEAD del processo 14bf7298904f2fc1e5e9e42966f7965e50e00028, collectorDirty false.
Vecchio collector :8082 PID 15280 fermato solo dopo identità/ricevuta null
verificate; :8080 PID 5676 e Windows ICS preservati. Nessun TLS, SDK, invocazione
native o cattura. Usare ora http://192.168.1.5/status per stato del receiver.
L'unica azione fisica richiesta: Browser TV → http://vidaahub.com → Raccogli una
volta. Le istruzioni :8082 sotto sono storiche. Leggere l'aggiornamento finale
di research/bridge-source-acquisition-20260930.md e l'eventuale report reale.

## Ultimo esito TV: pagina collector non aperta

L'utente riferisce che l'URL collector :8082 non si apre e la TV dice
«impossibile». Al controllo successivo receiver :8082 attivo, receipt null.
Ritirata l'indicazione di aprire quell'URL: il canale dal nome vidaahub della TV
al PC non era verificato. Non richiedere di riprovare lo stesso URL o la radice
come se caricassero automaticamente il collector. Il dominio citato da WeinzII
è il contesto del toolkit; non instrada da solo una nuova pagina al ricevitore.
La sola frase «impossibile» non distingue DNS, connessione, porta o protocollo.
Nessuna nuova misura delle API o dei permessi. Dettagli nell'ultimo aggiornamento
di research/bridge-source-acquisition-20260930.md. I paragrafi sotto che propongono
quell'azione fisica sono storici e superati da questa correzione.

## Aggiornamento operativo successivo: collector implementato

Leggere anche `research/bridge-source-acquisition-20260930.md` integralmente.
Ora esiste `sidee.py --bridge-source-check --check-port 8082`, collector
`web/bridge-source-check.js` e ricevitore separato `bridge_source_check.py`.
Test off-TV passati. La lacuna scelta è script caricati visibili in resource
timing ma fuori da document.scripts; raccolta singola esplicita, senza native
API, SDK execution, DNS/TLS, filesystem TV, inventario o vecchi auto-probe.
Receiver verificato su 192.168.1.5:8082; ricevitore post-Store :8080 preservato.
Alla preparazione `/status` receipt null: non dichiarare nuova prova TV.

Prima di proseguire controllare `/status` del nuovo ricevitore e leggere eventuale
`reports/bridge-source-latest.json`. Provenienza include build, Git HEAD/dirty,
hash sorgenti/report, origine effettiva e completezza. Analizzare gli script
localmente senza eseguirli. Non ripetere la raccolta se esiste già una ricevuta.
Raccolta nel contesto vidaahub mediante instradamento già presente, se accessibile:
http://vidaahub.com:8082/bridge-source-check.html → Raccogli una volta.
Non attivare nuovo spoof DNS/TLS o sostituire con un test LAN della stessa domanda.
HTTP/8082 differisce dal vecchio HTTPS/443. Se il nome non arriva al ricevitore,
registrare precisamente quel blocco del canale, non una mancata autorizzazione.
Il collector non può inserire codice nel Browser/Store remoto né leggere processi
di sistema; se non emerge sorgente utile, non inventare un nuovo servizio/API.

Il testo seguente è la consegna originale; le sue frasi "nessun nuovo collector"
descrivono lo stato precedente e sono superate da questo aggiornamento.

Continua il lavoro su Sidee in `C:\Users\empi0\Desktop\Sidee` e Nuvio in
`D:\nuvio\nuviotvsmart`. Svolgi tu il lavoro. L'obiettivo è **installare Nuvio
come vera app sulla mia Hisense 50E77NQ**. Se le informazioni disponibili non
bastano, **modifica Sidee per acquisire dalla mia TV i dati specifici mancanti**
e usali per proseguire. Non fermarti a una nuova analisi che dice "mancano dati"
o a una lista di cose che dovrei fare io. Non promettere una soluzione se le
prove non la sostengono.

Prima di modificare o eseguire test, leggi **completamente** questi documenti:

1. NEXT_CHAT_PROMPT.md;
2. AI_CONTEXT.md;
3. LATEST_RESPONSE_AND_NEXT_CHAT.md;
4. README.md;
5. VIDAA_FEASIBILITY.md;
6. research/post-store-result-20260930.md;
7. research/vidaahub-context-20260930.md;
8. research/vidaa-context-comparison-20260930.json;
9. `D:\nuvio\nuviotvsmart\VIDAA_STATUS.md`;
10. research/tv-acceptance-20260930.md;
11. research/vidaa-edge-context-review-20260930.md;
12. research/install-methods-q0707-20260930.md;
13. research/alternative-install-check-20260930.md.

Questo prompt e il riepilogo corrente prevalgono sui vecchi piani in cronologia.
L'ultima richiesta dell'utente è preparare questa consegna: **nessun nuovo
collector o test TV è stato implementato durante la preparazione del prompt**.

## Obiettivo verificabile e vincoli

TV Hisense **50E77NQ**, firmware `V0000.09.60A.Q0707`, VIDAA U09.60,
MTK9603, Odin/Chromium 111; modello interno storico 50E70LEVS_0003.
Per chiamare il risultato riuscito occorrono:

- voce propria nel launcher;
- frecce/OK/Indietro senza cursore;
- persistenza dopo riavvio reale;
- interfaccia caricabile e funzionante con PC, Sidee e server locale spenti;
- riproduzione di un contenuto autorizzato.

Tutti i criteri sono ancora **non verificati**. Internet per account/contenuti è
ammesso; non voglio ospitare l'UI sul mio PC/server. Se una strada dipende da UI
ospitata da un fornitore, dichiaralo e verifica quella dipendenza. Bookmark,
fullscreen, callback positivo, cache e service worker non bastano a dimostrare
installazione o disponibilità delle risorse dopo il riavvio.

Autorizzo test e controlli sulla mia TV e modifiche a Sidee/Nuvio. Non richiedere
nuovamente un consenso generico già dato. Non usare devkit, Superdesign, Media
Station X, contatti/percorso partner VIDAA. Non progettare bypass di firme,
autenticazione o AppConfig, impersonazione di identità/origini privilegiate,
né sostituzione ingannevole di app Store. Una risposta di diniego è un dato da
conservare, non una protezione da aggirare.

## Da dove ripartire

Lavora **sul codice e sui dati locali**, come richiesto nell'ultima correzione;
non ripetere ricerche online. Il riferimento vidaa-edge è
https://github.com/weinzii/vidaa-edge, già analizzato alla revisione
`94c3134911cbd4b813eea1f88c56819c0981518b` nei documenti.

**vidaahub.com resta prioritario come contesto di esecuzione/API**, non come
portale pubblico di installazione. Sulla TV Q0707 in quel contesto le API erano
già esposte ma le operazioni provate erano negate. Non sostituire questa
indagine con un altro test localhost/IP LAN. Un diverso indirizzo che dia
permessi rimane un'ipotesi, non una soluzione da tentare alla cieca.

La diagnosi già dimostrata è questa:

- Hisense_installApp legacy e Hisense_installApp_V2 convergono sullo stesso
  helper e su installApplication. Nei tentativi conservati: fileRead true/0,
  installApplication false/503, "client request permission check error, please
  check appconfig", SDK 1.5.0; callback 0 nonostante il fallimento. Il controllo
  iniziale del tipo oggetto V2 era passato; validazioni successive restano ignote.
- Il metodo upstream **New (File System) è diverso dalla funzione native V2**.
  Usa una scrittura già respinta nel no-op del 26 settembre; non ripeterla.
  I due metodi upstream registrano metadata/URL, non trasferiscono il bundle.
- Nel ramo package di vowOS.store.installApp, il return true precede l'esito
  asincrono. Dopo pkgmgr ret:true, il wrapper chiama comunque legacy per il
  launcher; il callback package può restare positivo anche se il launcher fallisce.
  Audit riproducibile in research/audit-vidaa-install-contract.mjs e risultato
  research/vidaa-install-contract-20260930.json: quattro scenari offline passati.
  Questo non dimostra un'installazione package sulla TV né il 503 per ogni payload.
- Sono stati scanditi 65 report JSON locali, incluse copie: non 65 sessioni
  indipendenti. I wrapper store/service selezionati sono stati letti completi.
  I transport wrapper non contengono l'implementazione nativa delle autorizzazioni.
  Non è stato trovato uno stager/schema d'import proprio verificato o il codice
  nativo AppConfig nel materiale disponibile. Non dedurre impossibilità universale.

## Compito operativo: soluzione oppure acquisizione mirata tramite Sidee

1. Controlla lo stato Git e la copertura dei report/sorgenti già acquisiti.
   Scegli **una lacuna concreta** il cui contenuto possa distinguere un metodo
   utilizzabile da uno già escluso. Spiega brevemente cosa manca e quale decisione
   consentirà; poi lavora, senza limitarti a proporre un piano.
2. Se i dati bastano a una candidata consentita, implementa il necessario e
   prova prima una app minima propria con ID/versione riconoscibili. Se non
   bastano, esamina sidee.py, web/app.js e i collector isolati esistenti, quindi
   **implementa un'acquisizione mirata in Sidee**, se tecnicamente possibile.
   Non avviare indiscriminatamente i vecchi startup probe.
3. Possibili dati utili, da scegliere solo dopo aver verificato ciò che manca:
   sorgenti complete di script già caricati e accessibili, troncamenti/excerpt
   mancanti, informazioni di versione e caricamento del bridge; contratto reale
   di un importatore/stager per app proprie eventualmente presente; diagnostica
   accessibile del rifiuto e dei suoi prerequisiti; prove delle risorse realmente
   conservate di una propria app di prova. Non inventare endpoint/metodi/schema.
   L'acquisizione deve usare osservazioni passive o letture consentite già
   identificate. Non scandire arbitrariamente filesystem/namespace SDK, non
   raccogliere credenziali, chiavi di firma o identità di altre app, non lanciare
   codice SDK estratto indiscriminatamente. Gestisci esplicitamente i dinieghi.
4. Se realizzi il collector: modalità isolata, avvio esplicito di una singola
   raccolta, dati limitati alla lacuna scelta; salva build/commit del collector,
   firmware se disponibile, origine effettiva, timestamp, hash e completezza.
   Distingui assente, troncato, non disponibile e negato. Mantieni i report grezzi
   locali e pubblica solo evidenze necessarie senza dati sensibili.
5. Verifica il collector fuori dalla TV con controlli pertinenti, poi esegui la
   raccolta sulla mia TV attraverso il canale effettivamente disponibile.
   Il consenso esiste già. Non dichiarare eseguita una prova senza ricevuta.
   Se manca un passaggio fisico non automatizzabile, chiedi **solo quell'azione
   precisa**, dopo aver preparato tutto il resto. Non chiedere un nuovo inventario
   generico, un generico screenshot o di riprovare hisense://debug.
6. Analizza subito il dato raccolto e continua verso la candidata. Distingui
   **API esposte, operazioni effettivamente autorizzate e risorse persistenti**.
   Valida separatamente esito package e registrazione launcher. Con un metodo
   consentito concreto, prova launcher/telecomando e poi riavvio con host spenti.
   Se nessuna candidata emerge, consegna il collector implementato, la ricevuta
   acquisita o il blocco tecnico preciso, e il prossimo test che lo può risolvere.
   Non presentare un altro audit offline come soluzione installante.

## Prove esaurite e stato da preservare

- **hisense://debug già provato dall'utente**; esito puntuale non comunicato.
  Non riproporlo e non inventare l'errore. Le vecchie domande UI sono superate.
- Risposta TV del 30 settembre già ricevuta: reports/post-store-20260930-120901-112525.json
  e post-store-latest.json, 4281 byte, SHA256
  `78b8bc5564464bc9d17b823b482d6b3d94cebfe7d22f31e094da21229841ab4f`.
  HTTP LAN: app API UNAVAILABLE, package READ_OK, 18 componenti di sistema.
  Non inventario Store completo né byte delle risorse. Metadata Duplecast del
  26 precedono l'operazione Store del 29; stato attuale delle risorse inconclusivo.
  Non ripetere inventario o probe esauriti identità/AppInfo/HSPDK/file.
- HTTPS già visibile dopo NAT: 382 record, FILTERED_FLOW_VISIBLE_AFTER_NAT.
  Non rifare la cattura già risolta; visibilità dei flussi non è lettura del corpo
  cifrato. Non ripetere DNS automatico/apertura della radice pubblica: piano ritirato.
- Test secondario UI Nuvio su :8181 preparato e fermato, nessun risultato TV.
  Codice conservato in nuvio_tv_check.py e web/nuvio-tv-check.js; non sostituisce
  installazione né indagine del contesto vidaahub.
- Ricevitore :8080 ultimo PID verificato 5676, LAN 192.168.1.5, non loopback;
  UDP 53 PID 6844 era Windows SharedAccess/ICS. Verifica lo stato corrente prima
  di intervenire. Hosts PC preesistente `192.168.1.8 vidaahub.com`: preservato.
- Sidee main, HEAD prima di questa consegna
  `513f85ea8646ba0628699781cd3d446fb94afca7`; ricava HEAD corrente da Git.
  **control/request.json è in staging dell'utente: non aggiungerlo, committarlo
  o resettarlo.** Blob `aefa724c1725b1ef2178c79fdd8914745bb9065e`, SHA256
  `6d8cd6ec102dd17b4ebd110e443fe6a68d645eee663ed1ce05fc2749699fa9b4`.
- Nuvio main HEAD `1f1ad284a292c06b0ed6b045dd1e1f3177666d1b`: conserva le
  modifiche locali a installer/index.html, scripts/package-vidaa.mjs e il nuovo
  VIDAA_STATUS.md. Corretti falsi successi/promesse; nessun nuovo build/ZIP,
  commit Nuvio o installazione TV. Controlli off-TV passati, non prova dei permessi.

Aggiorna NEXT_CHAT_PROMPT.md, LATEST_RESPONSE_AND_NEXT_CHAT.md, AI_CONTEXT.md e
le valutazioni pertinenti con evidenze, limiti e prossimo test decisivo.
**Committa Sidee su main con percorsi espliciti escludendo control/request.json**,
preservando tutte le modifiche locali. Non fare push senza richiesta.
La risposta finale deve dire cosa hai realizzato/acquisito, cosa è provato sulla
TV e cosa impedisce ancora la vera installazione. Niente promesse senza prova.
