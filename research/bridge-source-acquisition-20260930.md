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
