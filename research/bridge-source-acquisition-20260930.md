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
- riferimenti file/data/blob restano fuori scope: si conserva solo lo schema,
  senza percorsi di sistema o contenuti incorporati; non invalidano la ricevuta;
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

## Esito successivo della navigazione TV e istruzione ritirata

L'utente riferisce: «non apre la pagina su tv, dice impossibile», e chiede se
WeinzII non indichi soltanto vidaahub.com. L'URL richiesto era
http://vidaahub.com:8082/bridge-source-check.html. Questo è un tentativo di
navigazione fallito riferito dall'utente, non una raccolta sorgenti eseguita.

Controllo locale successivo: /status HTTP 200 su 192.168.1.5:8082,
collectionId bridge-216b0013fee4413595a1951b522aa615, buildId
bridge-fd277d6df6e660cf, Git HEAD del processo c329e8c50f94a6766894fb76a4c75514b6e26bc4,
collectorDirty false, receipt null. Nessun bridge-source-latest.json presente.
Listener :8082 PID 15280 e :8080 PID 5676 preservati. Nessuna modifica hosts,
config, DNS/TLS, SDK o collector e nessun nuovo probe/installazione TV.

Il receiver disabilita i log ordinari HTTP: receipt null prova che non è stata
accettata una raccolta, non prova l'assenza di ogni GET o tentativo di connessione.
Il messaggio generico «impossibile» non distingue risoluzione del nome, rete,
porta, protocollo o altre condizioni del Browser. Non inventare la causa.

L'indicazione di aprire l'URL è ritirata: l'assistente non aveva verificato il
prerequisito di instradamento della TV al PC prima di richiedere l'azione.
La radice vidaahub.com del toolkit e la nostra pagina HTTP su porta 8082 non
sono lo stesso ingresso. Il nome citato da WeinzII descrive il contesto delle
API, ma non crea il servizio/routing necessario a ospitare il collector.
Aprire la sola radice non caricherebbe automaticamente questa implementazione.
Non richiedere di riprovare i due indirizzi come soluzione già predisposta.

Blocco tecnico attuale: nessun canale verificato per caricare questo collector
nel Browser TV nel contesto vidaahub; il receiver può solo rispondere a richieste
che lo raggiungono, non navigare la TV o inserire codice in una pagina diversa.
Il precedente 503 resta una prova distinta, già raccolta in HTTPS vidaahub.
Le indicazioni di apertura sopra sono storiche e superate da questo esito.

## Richiesta successiva: root vidaahub predisposta sul PC

L'utente richiede esplicitamente di risolvere l'accesso e spostare il collector
su vidaahub.com, richiamando nuovamente weinzii/vidaa-edge. Questa richiesta
supera la precedente indicazione di non correggere il routing locale. La
raccolta rimane passiva: nessun SDK/native call o uso dei metodi negati.

Fatto nuovo verificato: il DNS Windows ICS 192.168.137.1 rispondeva A
192.168.1.8 per vidaahub.com, mentre ipconfig conferma questo PC Ethernet
192.168.1.5 e hotspot 192.168.137.1. La risoluzione ICS coincideva con il
mapping obsoleto hosts. Questo documenta un problema concreto del percorso
disponibile; non prova quale cache/resolver usasse la TV nel tentativo fallito.

Avviato il solo receiver isolato con --check-port 80: root `/` serve già la
pagina collector, nessun redirect né vecchio app.js. PID 14152 su 192.168.1.5:80.
CollectionId bridge-14ce9d228c2846b9b5b9351dc88de973, build invariata
bridge-fd277d6df6e660cf, Git HEAD del processo
14bf7298904f2fc1e5e9e42966f7965e50e00028, collectorDirty false.

Il primo tentativo diretto sul file hosts è stato negato da Windows, non
dall'auto-review. Preparato setup_bridge_domain.ps1, verificata sintassi e
avviato nascosto con elevazione UAC: successo registrato 2026-09-30T16:46:48Z.
Helper vincolato al SHA256 completo atteso e alla sola riga .8 vidaahub.com;
backup byte per byte prima della modifica, confronto successivo conferma che
non sono cambiati altri byte. Nessun servizio fermato, altri domini modificati
o policy permanente cambiata. Cache resolver Windows aggiornata.

Backup locale reports/bridge-domain-hosts-before-admin-20260930-184647.bin,
ignorato da Git insieme a tutti i record bridge-domain. SHA256 hosts prima
0e3808b0b86f0cdb61e1b6b71b50d9761d1e6f19fc9cc3c31e6fec817043b848,
dopo 39324dd84e1133b284741d78ad68d38137061aa08008edd71ef292736a0a91a4.
Non rieseguire il helper su un hosts successivamente modificato.

Verifica: DNS ICS A 192.168.1.5; GET dal PC tramite
http://vidaahub.com/ HTTP 200, contiene solo script collector. Manifest/status
disponibili su porta 80, receipt null alla preparazione. Report PC di readiness
in reports/bridge-domain-readiness.json, non una raccolta TV. Vecchio :8082
PID 15280 fermato dopo verifica identity e receipt null; post-Store :8080
PID 5676 e ICS UDP53 PID 6844 preservati. Nessun nuovo test di installazione,
inventario, capture HTTPS, TLS/certificato o probe nativo.

Azione fisica ora predisposta: **Browser TV → http://vidaahub.com → Raccogli
una volta**. URL senza porta o percorso. Non chiedere DNS automatico, debug o
inventario. Se il browser impone HTTPS, questo server HTTP non lo supporta:
registrare quel fatto senza bypass certificati. Attendere la ricevuta reale
su http://192.168.1.5/status e leggere subito gli script locali senza eseguirli.
HTTP/80 è distinto dal vecchio HTTPS/443; nessuna equivalenza di bootstrap,
permessi o persistenza è promessa. La scrittura 503 resta un dato precedente.

## Correzione del launcher Windows dopo il log utente

Il log successivo mostra il vecchio avvio Store/DNS e WinError 10048 UDP53.
Letto start-windows.bat: elevava il processo, aggiungeva regole firewall,
fermava tutti i processi con sidee.py nella command line (senza verificarne
modalità/ricevuta), poi eseguiva sidee.py senza flag isolato. Al controllo
successivo :80 e :8080 non avevano listener; ICS UDP53 PID 6844 restava attivo.
Nessun bridge-source-latest.json presente. Il receiver predisposto non era
quindi resistente a quell'avvio normale; correggere soltanto il server non
aveva completato il percorso di avvio Windows.

start-windows.bat ora sceglie Python con un flusso sequenziale affidabile,
quota il runtime bundled, esegue soltanto
sidee.py --bridge-source-check --check-port 80 e lascia aperta la finestra.
Rimossi elevazione, firewall, stop globali e avvio DNS/Store. Nessun servizio
Windows fermato. Il normale ingresso collector precede sempre i worker Git.

bridge_source_check.serve gestisce la porta occupata leggendo al massimo 64 KiB
di /status dal receiver locale: solo mode isolato e hash file identici permettono
il riuso. Nessun nuovo processo/ricevuta se quello conforme è già attivo; servizio
estraneo o build diversa produce errore senza stop. Binding Windows esclusivo
evita condivisioni imprevedibili di porta dovute a SO_REUSEADDR.
sidee.py presenta gli errori di avvio con esito nonzero e senza vecchio flusso.

Test HTTP reale off-TV aggiornato: seconda chiamata serve dopo report raccolto
preserva byte, collectionId e receipt; build differente respinta, server e report
restano disponibili. Fixture solo in directory temporanea. Parsing Python e
diff passati. JavaScript invariato, nessuna nuova operazione TV.

La readiness finale del launcher e i PID/provenienza operativi sono nel
record locale reports/bridge-domain-readiness.json. Il vecchio ricevitore
post-Store è fermo: il tentativo di ripristino è stato respinto dall'auto-review
per rischio di ripetere inventario/probe già esauriti senza autorizzazione chiara.
Il comando respinto non è stato eseguito; nessun workaround o nuovo tentativo.
Chiesta separatamente autorizzazione specifica o scelta di lasciarlo fermo.
Il collector :80 non dipende da quel processo. Non ripetere inventario o cattura.
L'azione resta Browser TV → http://vidaahub.com → Raccogli una volta.

Avvio reale del BAT corretto verificato dopo commit 100d4b0: root via dominio
HTTP200, solo collector, PID2312. Secondo avvio reale con stdin nul riusa
esattamente PID/collectionId; nessuna chiusura del server o DNS. Collection
bridge-d424a584b261425db1be7176edd852fd, build bridge-2f188c3d729a2bc3,
HEAD100d4b0e2f6c00a1df38e070dc4865b755f17c05, collectorDirty false, receipt null.
Nessun bridge-source-latest.json nuovo. ICS UDP53 PID6844 resta attivo.

Il report post-store-latest già presente non è più la copia delle 14:09:
timestamp pagina 2026-09-30T16:20:15.65Z, ricevuto 18:20:10.899852 Europe/Rome,
4281 byte SHA256 0efd7bac0e62b3c19b46141e1844d0127d07d14c086ddc531cd5c30c2370d2ba.
Questo fix non lo modifica e non ha lanciato quella raccolta. Non attribuire
questo report al nuovo collector o usare il vecchio hash per la copia latest.

### Ripristino autorizzato del receiver storico

L'utente risponde «autorizzo il ripristino». Nuovo avvio approvato del solo
sidee.py --post-store-check, nascosto: PID9552 su 192.168.1.5:8080. GET /status
mode post-store-check verificato; hash post-store-latest invariato
0efd7bac0e62b3c19b46141e1844d0127d07d14c086ddc531cd5c30c2370d2ba. Nessuna
navigazione TV verso quel receiver, POST snapshot, inventario, capture o DNS.
Collector :80 PID2312 e collectionId bridge-d424a584b261425db1be7176edd852fd
preservati, receipt null; ICS UDP53 PID6844 intatto. Record readiness aggiornato.
Il precedente diniego auto-review è risolto dall'autorizzazione specifica.

## Errore nome TV e verifica DNS delle due interfacce

L'utente riferisce «failed to load page name not resolved». Nessuna nuova
raccolta: /status via http://vidaahub.com ancora HTTP200, stessa collection/PID2312,
receipt null. :8080 PID9552 e ICS UDP53 PID6844 ancora attivi.

Query DNS esplicite dal PC, senza cambiare resolver o avviare capture:
192.168.137.1 per A vidaahub.com risponde 192.168.1.5; query a 192.168.1.5 per
A termina con connessione interrotta. Il vecchio messaggio DNS TV .1.5 si
riferiva al server Sidee storico, che qui è disabilitato; ICS serve l'hotspot
sul suo .137.1. Non attribuire UDP53 wildcard a un servizio DNS funzionante
su ogni interfaccia. Query AAAA su ICS riporta nome inesistente: conservare
il negativo distinto dall'A positivo; non dichiarare equivalenza o causa unica.

ipconfig conferma hotspot .137.1/Ethernet .1.5. ARP contiene .137.158 coerente
con il client TV storico, non prova del resolver scelto oggi. Chiesta rete TV
hotspot/router tramite domanda specifica; setting effettivo non disponibile.
Per il collegamento hotspot il passo fisico mirato è DNS primario .137.1,
chiudere/riaprire Browser, poi http://vidaahub.com. Il launcher ora stampa
questa istruzione locale specifica. Nessun DNS automatico, debug, inventario,
IPv6 disabilitato o stop ICS. Se fallisce anche con rete/DNS confermati, il
negativo AAAA e la cache/resolver Browser restano aspetti da distinguere.

## TV confermata sulla rete router: DNS LAN indipendente

L'utente corregge l'ipotesi hotspot: TV e PC sulla rete router, come nel
meccanismo locale di weinzii/vidaa-edge già analizzato. L'indicazione .137.1
non è applicabile qui. Il prerequisito è un DNS che risponda sul PC LAN .1.5,
non soltanto un HTTP server o il mapping hosts usato dal resolver del PC.

Prova nuova di bind, non di API: socket UDP esclusivo su 192.168.1.5:53
disponibile nonostante la precedente entry ICS wildcard. Nessun SO_REUSEADDR
forzato, stop/disabilitazione ICS o reconfigurazione NAT/DoH/IPv6.
Implementato lan_dns.py, processo separato dai worker storici:

- bind esclusivo UDP e TCP allo specifico .1.5, clienti solo .1.0/24;
- solo vidaahub.com A .1.5; AAAA/HTTPS e altri tipi NOERROR/NODATA;
- altre richieste inoltrate al router .1.1, senza cattura/log dei loro nomi;
- marker TXT locale con hash per il riuso della propria versione, non un
  servizio VIDAA; framing/limiti e 16 worker, nessuna chiamata TV;
- status locale limitato ai tentativi sul solo nome target, PID/hash/ultimo
  client e tipo; una query dal PC non equivale a ricezione TV;
- --background avvia nascosto e conferma entrambi i trasporti prima di
  restituire; versione estranea non viene fermata o sostituita.

start-windows.bat ora avvia/riusa quel DNS LAN prima del collector, con i valori
locali espliciti noti; fallisce chiaramente se non ne verifica la salute.
Test off-TV UDP/TCP reali su loopback: A, AAAA/HTTPS NODATA, forwarding a un
upstream fittizio su entrambi i trasporti, richieste fuori subnet respinte,
malformate gestite e bind doppio respinto senza danneggiare il server.

Prima sonda/avvio nella restrizione di rete del tool: timeout health/inoltro
pur con bind corretto. Sonde locali fuori da tale restrizione hanno confermato
il server; il solo DNS nuovo PID3412 è stato poi riavviato dopo verifica del
percorso esatto/hash, per permettere l'inoltro al router. Una chiamata
Stop-Process aveva errore interno; completato con il solo handle di quel PID,
nessun altro processo toccato. DNS finale PID20404, .1.5:53 UDP/TCP; A .1.5
su entrambi, AAAA/HTTPS NOERROR/NODATA verificati. Query example.com via DNS
locale inoltrata al router e riuscita, non ricerca di metodi TV. Launcher
reale verificato per riuso di DNS/collector, da ambiente con accesso rete locale.

Tentativo opzionale di nuove regole LAN UDP/TCP ristrette: UAC annullata
dall'utente, helper non eseguito e ritirato. Nessuna nuova regola applicata;
regole Private UDP53 esistenti preservate. Ethernet è Private. Non dichiarare
verificata l'accessibilità dalla TV sulla base delle sole sonde locali.

ICS servizio PID6844 resta RUNNING; collector :80 PID2312 con stessa collection
bridge-d424a584b261425db1be7176edd852fd e post-Store :8080 PID9552 intatti.
Receipt collector null alla preparazione. Readiness aggiornata con status/hash
DNS; il firmware resta riferimento storico, non nuova misura.

Azione fisica preparata per questa rete: **DNS primario TV 192.168.1.5 → chiudi
e riapri Browser → http://vidaahub.com → Raccogli una volta**. Non indirizzo IP
sostitutivo del contesto, hotspot imposto o nuova operazione native. Analizzare
immediatamente l'eventuale report senza eseguire sorgenti estratte.

## Nuovo fallimento: separazione delle evidenze DNS/HTTP

Utente: «non funziona ancora». DNS in esecuzione PID20404 osserva richieste
A vidaahub da 192.168.1.10 (targetQueries 8 all'ultima lettura), senza errori
nel log del processo; non ancora confermato l'IP TV. Il log conta richieste,
non attesta che il client abbia usato la risposta. Collector precedente PID2312
ancora HTTP200 dal PC, receipt null. Mancavano contatori degli accessi: una
ricevuta assente non permette di dedurre assenza di GET o caricamento script.

Implementati in SourceHTTPServer, indipendenti dalla raccolta:
- contatore di connessioni TCP accettate e di GET/POST per IP privato;
- conteggi per root, HTML/JS collector, manifest, status, snapshot; altri path e
  Host mascherati [OTHER], query scartate prima di ogni registrazione;
- massimo32 client, timestamp e stato locale ignored bridge-domain-http-status;
- snapshot disponibile in /status.httpAccess; errore di scrittura diagnostica
  tollerato per non impedire il caricamento della pagina.

Non è una nuova cattura HTTPS, un inventario o un probe SDK/native. Non conservati
header sensibili, cookie o body. Test reale HTTP e TCP passati: script servito,
query token non registrata, connessione senza HTTP distinta da richiesta;
isolamento, singola ricevuta idempotente e riuso/rifiuto build estranea invariati.
Regole firewall lette soltanto: presenti 54 Allow inbound TCP80 profilo Private,
Ethernet Private; nessuna regola Block inbound attiva nell'elenco consultato.
Questo non prova la raggiungibilità della TV né esclude filtri esterni.

Errore preciso attuale e conferma .1.10 richiesti con due domande mirate.
Attivare solo il receiver nuovo dopo verifica di identità/receipt; preservare
DNS20404, post-Store9552, ICS6844 e i file già acquisiti. Poi leggere accessi
e dati ricevuti: nessun esito installante dichiarato sulla base del test PC.

Attivazione completata: soltanto PID2312, vuoto, sostituito dopo controllo di
mode, collection/hash precedenti, executable/cmdline esatti e listener TCP80.
Nuovo PID19752, collection bridge-5194a818c1e14b96b7d4e5b858ce4465,
build bridge-6bbcea0ceaa98b5e, runtime HEAD339fa8e670348ddf12de04ade073dfb22bfe53da,
collectorDirty false, receiver SHA256
69d40333c13f9e04aef03efa6c21e803f3155ef302261439a3dc6d55ab5f9c5d.
DNS20404, post-Store9552 e ICS6844 confermati vivi, nessun cambio firewall.
Root via dominio e script HTTP200, pagina isolata verificata; prime registrazioni
HTTP solo da PC .1.5, receipt null. Questo intervallo non descrive i precedenti
tentativi TV senza contatori. Ultimo status DNS letto targetQueries9, client .1.10.
Readiness sostituita con fotografia corrente e provenienza, report post-Store
hash0efd7bac0e62b3c19b46141e1844d0127d07d14c086ddc531cd5c30c2370d2ba intatto.
Chiesto tentativo fisico esplicito http://vidaahub.com/ dopo riapertura Browser.
Nessun POST snapshot, nuova raccolta TV, native API o build Nuvio eseguiti.

## Risposta utente successiva: «name not resolved», TV .1.10

Prima delle sonde Windows, status DNS ancora targetQueries9/.1.10/1790792853,
2026-09-30T18:27:33Z (20:27 locale); clock PC alla verifica20:50:12 locale.
Non risultavano nuove richieste del nome target per il tentativo recente.
HTTP19752 conserva solo accessi PC .1.5 e receipt null. L'utente conferma
poi IP TV .1.10; le vecchie richieste provenivano quindi dalla sua TV.
Resolve-DnsName -Server .1.5 -DnsOnly -NoHostsFile verifica con un resolver
indipendente dalla funzione exchange del codice: A .1.5 TTL30, AAAA senza
record né errore, marker TXT esatto del proprio hash d0616fe...ee961.
La sonda A aggiorna targetQueries10/clientPC: conservarne questa attribuzione.
Processo DNS20404/percorso/cmdline e bindUDP .1.5 confermati in sola lettura;
regole Sidee Allow inbound Private UDP53 con indirizzi e programma Any.
Nessuna regola cambiata, processo riavviato o nuovo test TV/native/capture.

La risposta DNS è accettata dal resolver Windows, ma non è provata la risposta
usata dalla TV nel tentativo recente. Campo DNS primario TV ancora richiesto
separatamente: l'utente alla domanda raggruppata aveva fornito soltanto l'IP.
Nessun presupposto che un'opzione preselezionata sia stata confermata.
Blocco osservabile prima di HTTP; selezione del resolver/cache o diverso nome
effettivo da distinguere prima di intervenire. Non chiamarlo nuovo rifiuto
AppConfig/installazione, né difetto certo del router o della risposta DNS.

## DNS primario confermato e correzione della diagnostica

L'utente risponde .1.5 al campo DNS primario, dopo conferma IP TV .1.10.
Queste impostazioni sono risolte; non ripetere le domande. Nel codice è stato
individuato un difetto reale: note_target scriveva il file prima di restituire
la risposta, senza gestire OSError. Un registro bloccato poteva impedire anche
il send DNS. Nel log storico non c'è un errore che provi questa causa sulla TV.

Corretto: errori di persistenza tollerati e contati; rimosso il throttle che
non salvava l'ultimo evento di un burst. Status ora separa fino32 client solo
per vidaahub, con query, repliesSubmitted/replyErrors, tipo, UDP/TCP, timestamp,
rcode e count risposta. Il send viene registrato dopo sendto/sendall, compresi
errori di socket. Nessun payload/query/altro nome conservato. Submitted significa
accettazione del send da parte del socket locale, non risposta ricevuta dalla TV.

Tre test passati: routing/NODATA/forwarding e bind esclusivo già presenti;
burst TV+PC conservato/esito send negativo/altro nome non registrato;
registro bloccato con PermissionError durante replace, risposte UDP/TCP reali
ancora corrette e contatori memoria coerenti (4errori log, 2send riusciti).
Nessun SDK o API TV chiamato dai test.

Attivazione controllata: vecchio20404 verificato con marker TXT/hash d0616fe...
ee961, percorso/cmdline Python e ownership del bind .1.5:53. Backup status in
reports/bridge-domain-dns-before-send-metrics.json ignorato; fermato soltanto
20404, nuovo10028 nascosto. SourceSHA
c61f8b01b713153a9ddf8781ce2429fbbca942da6e6be1b6aa97b32689d49231.
HTTP19752, post-Store9552 e ICS6844 verificati vivi e preservati. Windows resolver
senza hosts: A .1.5 TTL30 su UDP/TCP, AAAA senza record né errore. --background
riusa la nuova versione; status iniziale solo PC .1.5, 3query/3submitted/0errori,
statusWriteErrors0. Nessun cambio regole firewall, router, DoH o IPv6.

Chiesto all'utente riavvio elettrico (staccare corrente30s) e riapertura esplicita
http://vidaahub.com/ mantenendo DNS .1.5, per osservare un tentativo successivo
al riavvio del resolver TV. Non assumere in anticipo che la cache sia la causa
o che il problema sia risolto. Prima della conclusione leggere i nuovi contatori
TV .1.10, gli accessi HTTP e la ricevuta; usare subito eventuali sorgenti ricevute.
Nessun nuovo esito installante o criterio Nuvio acquisito alla preparazione.

## 1 ottobre: richieste HTTP della TV e salto HTTPS riferito

Avvio manuale utente del launcher. Stato di ieri HTTP19752 era un file residuo:
lettura live /status conferma nuovoHTTP2848, collection
bridge-c2f2b35c1a30469fbcfdd197f5602847, build6bbcea0ceaa98b5e,
runtimeHEAD12363152bda6975445c53f5d782ef51ea1cc44f5/dirtyfalse, receipt null.
Python processo python3.13.exe; percorso/cmdline non disponibili dalla sonda WMI.
DNS18896/hashc61f8...d49231; Ethernet Private, AllowTCP80 Private Any indirizzi/
programma/interfaccia letto, nessun cambio firewall. Listener TCP80 .1.5 PID2848,
nessun443/8080 osservato. Non riusare i vecchi PID9552/6844 senza verifica.

Durante il lavoro arrivate dalla TV .1.10 due connessioni/richieste GET / e JS,
Host vidaahub.com, timestamp finale2026-10-01T07:30:07.410680Z. DNS9query/9send/
0errori, ultima A rcode0/1answer, statusWriteErrors0. Accesso HTTP ora dimostrato;
richiesta dello script non prova sua esecuzione o visualizzazione. Nessun /manifest
o POST snapshot registrato. Utente prima pagina bianca, poi riferisce che clic
Raccogli porta a HTTPS. Il collector non assegna location e server non emette
Location/redirect; l'origine precisa del salto non è provata.

TLS locale esaminato soltanto via certificato pubblico: .sidee-certs/vidaahub.com.crt,
subject=issuerCNvidaahub.com, SANvidaahub.com/www, validità25Sep15:13:33Z-
25Oct15:13:33Z2026. Generatore storico usa req -x509. È auto-firmato, non una
catena pubblica fidata del dominio. Chiavi private non lette, nessun listenerTLS,
SNI hook/capture o scriptSDK avviato. Il vecchio run_https usa SideeHandler normale
e non può essere acceso come se fosse il collector isolato. Non impersonare
l'origine HTTPS VIDAA o aggirare la fiducia TLS per ottenere permessi negati.

Correzione consentita al client web ordinario:
- exportCommonJS condizionato all'assenza di window, così un module shim presente
  nel browser non salta la registrazione dei listener (causa TV non ancora provata);
- currentScript null usa il proprio tag identificato senza leggere API native;
- bottoni typebutton e preventDefault, niente navigazione o submit;
- manifest/upload/retry redirect:error e credentials:omit, errore visibile;
  letture delle sorgenti già usavano questi limiti e restano invariate.

Test JS esteso: VM con window e module.exports, currentScript null, location
immutabile e native getter che lanciano. Click/retry funzionano e riusano identico
body dopo errore upload; redirect respinto mostra errore senza cambiare location.
Fixture fonti/limiti/dinieghi passate, 2test HTTP receiver passati. Non sono prove
del browser TV, di HTTPS o dell'importazione Nuvio. Preservare ricevuta e dati
pre-fix prima dell'attivazione; registrare nuovo build/collection/PID live.

Attivazione completata dopo commitc8f6e13: mode/collection/preimageSHA e receipt
null del vecchio2848, file accessi localePID2848 e listener .1.5:80/2848 verificati;
ProcessNamepython3.13 confermato. Non disponibile il percorso WMI, perciò non
asserito: identità corroborata da mode/hash/collection e file generato dal receiver.
Salvati prima di fermare il solo2848 i due JSON bridge-domain-http-before-click-fix-
20261001 e bridge-domain-manifest-before-click-fix-20261001, ignorati da Git.
Nuovo HTTP7320 avviato nascosto con runtime bundled e modalità isolata; DNS18896
preservato. Collection bridge-4ae91e9a77d646749cc6eea99d66aefd,
build bridge-6ecf39c1d5849466/runtimeHEADc8f6e1395edee58a9364c0c431d8c665d37f3856,
dirtyfalse. JS SHA7c3a4809bb830a7666e9bb6c139ade45448f92ca87871f69acb1dd9d9ff4b6c5;
HTML SHAe360f8f62e0f042b92346c6b2298e0adabafedd6a092779e548ce226f06b67e4.
Root e JS HTTP200 dal PC, tipo bottoni e guard browser/redirecterror verificati,
receipt null. Readiness aggiornata e attribuisce i GET TV alla versione precedente,
non al fix ancora privo di una nuova prova TV. Nessun TLS o server Sidee normale.
