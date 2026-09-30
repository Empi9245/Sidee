# Nuvio sulla Hisense VIDAA 9: valutazione di fattibilità

Verifica: 2026-09-30, Europe/Rome. TV: Hisense **50E77NQ** (modello confermato
dall'utente durante la ricerca successiva), firmware `V0000.09.60A.Q0707`,
OS `U09.60`, MTK9603, Odin/Chromium 111.

Ultimo fix operativo: start-windows.bat avviava ancora il flusso storico e
fermava tutti i processi Sidee. Dopo il log utente :80/:8080 erano assenti.
Launcher corretto per il solo collector HTTP/80 e riuso del receiver conforme,
senza DNS/stop processi; ICS preservato. Test riavvio/conservazione ricevuta e
build estranea passati off-TV. Non cambia la diagnosi AppConfig o i criteri Nuvio.

Verificato anche avvio BAT reale e doppio avvio: receiver :80 PID2312 conservato,
root HTTP200, receipt null. :8080 fermo, riavvio bloccato dall'auto-review per
rischio di ripetere inventario esaurito; approvazione specifica chiesta. Questo
non impedisce la raccolta nuova su :80. Nessuna nuova prova TV del collector.

Autorizzazione specifica ricevuta dopo: receiver :8080 ripristinato PID9552,
report intatto, nessuna nuova raccolta. Collector :80 e ICS preservati.

Aggiornamento successivo alla richiesta esplicita dell'utente: collector ora
alla radice **http://vidaahub.com/**, HTTP/80. Corretto solo il vecchio mapping
hosts .8 → .5 con backup. DNS ICS verificato .5 e GET dal PC attraverso il
dominio HTTP 200; apertura/raccolta TV ancora da confermare. Nessuna nuova
operazione VIDAA né equivalente HTTPS/443; nessun nuovo criterio Nuvio provato.
Le indicazioni di ritiro dell'accesso sotto sono storiche, superate dal setup.

Ultimo esito TV: la pagina collector :8082 non si apre, messaggio riferito
«impossibile»; receiver attivo e receipt null. Ritirata l'istruzione di apertura
su un canale TV → PC non verificato. Non è una nuova prova di rifiuto AppConfig;
il livello preciso dell'errore di navigazione non è determinato. Il dominio
indicato da WeinzII non rende automaticamente raggiungibile il collector locale.

Aggiornamento operativo: implementato un
[collector isolato delle sorgenti già caricate](research/bridge-source-acquisition-20260930.md),
che copre anche resource timing, non registrato dai vecchi collector DOM.
Test off-TV passati e ricevitore :8082 pronto; nessuna ricevuta TV nuova.
Priorità vidaahub mantenuta senza cambiare DNS/TLS: l'accesso dal Browser TV
dipende dal canale già presente. La raccolta non legge l'implementazione nativa
AppConfig e non risolve da sola il rifiuto false/503 o il trasferimento risorse.
HTTP/8082 non è equivalente al vecchio HTTPS/443. Tutti i criteri restano aperti.

**Ultima richiesta:** prove dirette sulla TV, senza imporre una guida pubblica
per ogni controllo. Il test secondario Nuvio LAN è stato preparato e poi
fermato senza report TV: non sostituisce la priorità vidaahub. L'utente indica
vidaa-edge; [correzione del contesto](research/vidaa-edge-context-review-20260930.md).
Il suggerimento DNS automatico/sito pubblico era errato per quel meccanismo.
La condizione sotto riguarda un'importazione consentita, non ogni osservazione.

## Esito

**Correzione corrente:** hisense://debug era già stato provato, non riproporlo.
L'utente chiede studio del codice locale senza ricerche online. Scanditi 65 JSON
locali (con duplicati), letti i wrapper store/service. Ramo package → registrazione
Hisense_installApp dopo esito positivo; return/callback non garantiscono entrambe
le fasi. Quattro scenari offline sui corpi originali confermano callback positivo
anche con launcher fallito: [analisi](research/install-methods-q0707-20260930.md),
[audit](research/vidaa-install-contract-20260930.json). Nessuna nuova install TV,
schema/stager d'import proprio o implementazione AppConfig trovati nel materiale.
Il [controllo alternative](research/alternative-install-check-20260930.md) è storico.

[Diagnosi legacy/V2/New](research/install-methods-q0707-20260930.md): New upstream
non è l'API V2. Legacy/V2 condividono helper e backend installApplication; le
tracce TV mostrano lettura riuscita e poi rifiuto AppConfig 503. Non è un errore
del tipo oggetto V2; nessun nuovo permesso o import di risorse è stato dimostrato.
Le validazioni successive al gate restano ignote. Non ripetuti install/write.

Indagine prioritaria completata:
[vidaahub-context-20260930.md](research/vidaahub-context-20260930.md),
[confronto offline dei sei report](research/vidaa-context-comparison-20260930.json).
Le fonti pubbliche distinguono l'accesso al bridge nelle diverse generazioni;
non documentano una nuova autorizzazione Q0707 o un'origine sostitutiva per
importare Nuvio. vidaahub esponeva già install legacy/V2 ma falliva AppConfig 503.
Non c'è un A/B fra firmware né un confronto che isoli il solo hostname.
Prompt aggiornato in [NEXT_CHAT_PROMPT.md](NEXT_CHAT_PROMPT.md), stato e modifiche
locali Nuvio in [LATEST_RESPONSE_AND_NEXT_CHAT.md](LATEST_RESPONSE_AND_NEXT_CHAT.md).

Il PC ha un mapping hosts preesistente vidaahub.com → 192.168.1.8, preservato:
il suo timeout HTTPS non prova sito pubblico spento. DoH pubblico A/AAAA ha dato
NODATA al momento della verifica; non NXDOMAIN né prova universale. I sottodomini
Store già osservati non sono un nuovo ingresso da impersonare.

**Nessuna delle strade esaminate è attualmente dimostrata capace di soddisfare
tutti i requisiti senza devkit.** Questo è un limite delle evidenze e dei
meccanismi disponibili, non una prova che il firmware non possa mai eseguire
un'app locale autorizzata.

L'obiettivo resta Nuvio avviabile dal launcher, con frecce/OK/Indietro senza
cursore, persistente dopo riavvio e utilizzabile con Sidee e il server locale
dell'interfaccia spenti. Internet per contenuti/account è consentito. L'utente
non vuole gestire hosting dell'interfaccia. Browser fullscreen, segnalibri,
cache e service worker non sono una dimostrazione di installazione persistente.
Un eventuale servizio dell'interfaccia gestito dal produttore va dichiarato
come tale; non equivale a un pacchetto locale e non è una soluzione oggi provata.

**Vincoli aggiornati dall'utente:** niente contatto con VIDAA e niente percorso
partner. Media Station X è disponibile nello Store della sua TV, secondo la
risposta dell'utente, ma l'utente non vuole usarlo. Escluso dal percorso finale;
le verifiche sotto rimangono evidenze di ricerca, non una proposta di setup.

## Matrice aggiornata: evidenza, mancanza e prova decisiva

| Strada | Provato | Manca / dipendenza | Test decisivo | Abbandono |
| --- | --- | --- | --- | --- |
| Package/sideload proprio | archivio web Nuvio, non formato VIDAA accettato | import autorizzato Q0707, formato e storage; UI locale | app minima propria, launcher/D-pad, riavvio host spenti, playback autorizzato | bypass, devkit/partner, UI ancora dipendente dal PC |
| Contenitore persistente | identità native, tvbrowser locale; non file Nuvio | import di risorse proprie e persistenza documentati; MSX escluso | stessa prova, risorse/versione riconoscibili dopo riavvio | solo URL/cache/sessione o percorso escluso |
| UI del fornitore | registrazione URL pubblicata per altre app, port Nuvio hosted | servizio Nuvio operativo e distribuzione launcher autorizzata; hosting esterno | launcher/D-pad/riavvio PC spento e playback, dipendenza dichiarata | permesso negato, endpoint indisponibile o hosting richiesto all'utente |

**Prerequisito per installare oggi non soddisfatto:** importazione consentita di
una propria app sul firmware target, documentata o effettivamente offerta dalla
normale UI della TV. Si possono misurare UI/input prima di trovarla.
Solo dopo si prepara/importa una app minima con ID proprio e versione riconoscibile
e si esegue il test reale. Un altro indirizzo o snapshot LAN non lo sostituisce.
La procedura pubblica TVOЁ ispezionata usa ancora URL + Hisense_installApp e
callback 0; non prova permessi Nuvio o copia di risorse. L'issue vidaa-edge 30 resta
aperta; non c'è una correzione corrente documentata che risolva il gate su Q0707.
Nuvio locale ha ora messaggi installer/packager corretti e VIDAA_STATUS.md;
verifiche off-TV passate, nessun build/ZIP o nuovo test sulla TV.

## Verifiche precedenti — senza partner e senza MSX

### Verifica attuale sulla TV — risultato parziale ricevuto

**Aggiornamento: risposta ricevuta alle 14:09 del 30 settembre, Europe/Rome.**
Provenienza e limiti in [post-store-result-20260930.md](research/post-store-result-20260930.md).
Origine HTTP LAN; API elenco app UNAVAILABLE, API package READ_OK con 18
componenti di sistema, incluso tvbrowser type web. Nessun package con nome
Nuvio/Duplecast, ma manca il registro app corrente: questa assenza non prova
che Duplecast memorizzi solo metadata. Nessun nuovo importatore individuato;
la domanda sullo storage post-reinstallazione rimane inconclusiva. Le righe
seguenti descrivono la preparazione precedente alla risposta.

Dopo la richiesta esplicita di usare Sidee, verificati processi/listener e
connessione: Sidee era spento, localhost e `192.168.1.5:8080` rifiutavano
`/api/status`. Questo PC è ancora su `192.168.1.5`.

Preparata e avviata modalità `sidee.py --post-store-check`. Serve una pagina
dedicata e riceve gli elenchi attuali dalle sole API esposte
`Hisense_getInstalledApps()` e `vowOS.store.getInstalledPkgs()`. Nessun caricamento
SDK, override di identità/origin, accesso a file TV, install/write, DNS, vecchi
probe o catture. Test off-TV su risposte valide/negate/assenti e isolamento HTTP
passati. Il risultato TV non è ancora arrivato al momento della predisposizione.

La nuova lettura è motivata dall'operazione Store del 29 settembre, successiva
al registro dettagliato del 26. Obiettivo: trovare eventuali riferimenti a un
package o flag di packaging nello stato attuale, non ricercare nuovi permessi.
I campi potrebbero non essere esposti: assenza di riferimenti non equivale
all'assenza di file/cache. Questo test non legge byte delle risorse e non prova
un importatore autorizzato per Nuvio. Tutti i cinque criteri restano non verificati.

La pagina parte automaticamente quando l'utente apre `http://192.168.1.5:8080`
nel Browser della TV. Sidee non è un controllo remoto generale capace di aprire
autonomamente la pagina sulla TV. `/status` mostra l'ultimo risultato; i file
sono locali in `reports/post-store-latest.json` e history, senza sync Git.
Se entrambe le API sono indisponibili, la pagina lo mostra senza salvare un
falso report TV. Nessuna nuova reinstallazione Duplecast è richiesta.
La successiva richiesta sull'origine ha portato a registrare origin/protocol/
hostname/secureContext del browser e Host/Origin HTTP del ricevitore. Il server
rimane sull'IP LAN; nessuna sostituzione DNS/TLS di un dominio VIDAA attivata
per ottenere privilegi. Il vecchio contesto vidaahub.com esposto nei report
aveva comunque respinto install/write con AppConfig 503. Origin e disponibilità
API non equivalgono a permesso di importare un'app.

Ricerca del 30 settembre, Sidee `main` inizialmente `ef25a23`, Nuvio `main`
`1f1ad284` pulita. Nessuna nuova sessione sulla TV; ultimo report e relativo
commit restano quelli elencati nella sezione Report verificati.

### Prova del servizio di risorse MSX fuori dalla TV

Esaminato il JavaScript pubblico collegato dalla documentazione MSX:
[tvx-plugin.min.js](https://msx.benzac.de/js/tvx-plugin.min.js), versione
0.0.79, 101.333 byte, SHA256
`7cf9daabeb7787094433f7958fed41d2bedc561496e987d01fc070c6a0183684`.
Il test riproducibile [audit-msx-container.mjs](research/audit-msx-container.mjs)
estrae soltanto il BlobService revisionato, dopo controllo dell'hash, e usa
trasporto fittizio e una risorsa HTML sintetica. Zero richieste reali, nessun
server, nessun accesso TV e nessuna esecuzione dell'intero plugin.

Risultato salvato in [msx-container-audit-20260930.json](research/msx-container-audit-20260930.json):
`loadBlob` usa GET, `executeBlob` usa POST (non esegue un'app), le risposte e
gli object URL esistono nell'istanza corrente; una nuova istanza in un nuovo
contesto JavaScript non li recupera. Nessun accesso a localStorage/IndexedDB
durante il test; `clear` revoca gli object URL. **Questo BlobService non è un
importatore persistente.** Il test simula una nuova istanza, non un riavvio
della TV, e non esclude storage separato implementato da altre funzioni.

La documentazione [Video/Audio Plugin](https://msx.benzac.de/wiki/index.php?title=Video/Audio_Plugin)
spiega inoltre che anche il plugin visibile in iframe non riceve eventi tasto,
mouse o touch: non è sufficiente per l'interfaccia Nuvio. [Key Property](https://msx.benzac.de/wiki/index.php?title=Key_Property)
assegna azioni ai contenuti MSX; non documenta l'invio completo di frecce/OK/
Indietro all'iframe. [HTML5X Plugin](https://msx.benzac.de/wiki/index.php?title=HTML5X_Plugin)
è un player multimediale, non un importatore di app. Nessun loader costruito
su data URL, cache, aggiramento della validazione o ipotesi sui nomi delle API.

### Nuvio ospitato dal produttore: indirizzo reale, servizio non utilizzabile ora

Trovato un endpoint concreto, non inventato: `https://web.nuvioapp.space/`.
Il [wrapper ufficiale TizenBrew](https://github.com/NuvioMedia/NuvioTVTizenBrew/blob/f3851d9ff671cca0c6d48bc7bb79b8c7debbddcc/app/main.js)
lo usa in `window.location.replace`; anche index.html contiene il redirect.
Il commit corrente del wrapper è `f3851d9ff671cca0c6d48bc7bb79b8c7debbddcc`,
14 luglio 2026, 08:02:09 UTC. Il README lo descrive come wrapper di app ospitata.
La vecchia repo `NuvioMedia/NuvioWeb` ora rimanda a `NuvioTVSmart`: non è un
nuovo port locale separato. Il wrapper Tizen non è installabile su VIDAA.

La richiesta HTTPS diretta dal PC al servizio ha restituito **HTTP 522**;
anche il lettore web è andato in timeout. Questo risultato vale per il momento
e il punto di osservazione del test, non prova chiusura definitiva del servizio.
Non è stata caricata o testata l'interfaccia Nuvio da questo endpoint.

Esaminato anche `https://nuviovidaa.netlify.app/`, trovato in una segnalazione
pubblica: HTTP 200, pagina di 8.920 byte, SHA256
`b0b4cd5eb7088bd70d1bbf531b8c5f2ab59c214674b6538ecb10d68c92cead45`.
La pagina è un wrapper comunitario che ridimensiona e mette a fuoco un iframe
caricato dallo **stesso** `web.nuvioapp.space`. Conserva eventuali dimensioni
manuali in localStorage, non contiene il bundle Nuvio e non importa risorse
persistenti. HTTP 200 del wrapper non dimostra che Nuvio funzioni. Non è una
distribuzione ufficiale VIDAA; nessun account inserito e nessuna esecuzione TV.

MSX documenta `link:{URL}` per app HTML5 esterne in [Tips & Tricks](https://msx.benzac.de/wiki/index.php?title=Tips_%26_Tricks#External_HTML5_Games/Apps),
ma questo percorso è ora escluso dall'utente. Anche prima dell'esclusione
avrebbe richiesto servizio funzionante, verifica del contesto di apertura
(app o browser), input, ritorno e riavvio. Nessuna di queste prove è superata.
La disponibilità di un URL ufficiale corregge la precedente mancanza di un
indirizzo identificato; non risolve servizio, launcher VIDAA o storage locale.

### Manuale software della famiglia MT9603 / VIDAA U9

Scaricato l'[E-Manual ufficiale Hisense](https://hisense.cl/wp-content/uploads/2025/11/User-Manual-58Q6QV.pdf),
213 pagine EN/ES, 10.889.122 byte, SHA256
`7dcf27b9db2cb982c36fc51dda53a9cc0e330591177a43a42acbb7f94150bb02`.
Il risultato pubblico lo identifica come MT9603 VIDAA U9 NA/SA. È pubblicato
per 58Q6QV e altra regione: non è il manuale esatto della 50E77NQ EU/Q0707.
Lette completamente le pagine pertinenti di Home/Shortcuts, gestione app,
Browser, USB, Media/Media Format e App Issues; render e lettura visiva delle
pagine PDF 8 e 49, comprese le icone OK/Home.

- Shortcuts (pagina stampata 7): aggiunge un sito visitato dal Browser alla
  Home. È un collegamento browser, già escluso dai requisiti.
- USB (pagina 48) e Media (72–75): foto/audio/video, NTFS/FAT32 e registrazioni;
  nessuna procedura di importazione HTML/JS/CSS descritta in queste sezioni.
- App Issues (95): app compatibili e Store; distingue gli APK scaricati, che
  potrebbero non essere installabili. Non documenta un sideload Nuvio.

Queste sezioni non offrono una nuova strada locale; la loro assenza di istruzioni
non dimostra l'impossibilità universale di qualsiasi importatore sul firmware.
Riesaminati anche i nomi/URL delle 61 app nel report storico: nessuna nuova
funzione autorizzata di importazione emersa. Non trasformare la presenza di
Browser, Media, E-Manual locale, Plex o giochi in un'autorizzazione a sostituirne
risorse/identità. Nessun tentativo su package o database di app altrui.

**Esito della ricerca documentale:** nessuna nuova strada che soddisfi i requisiti
e i vincoli aggiornati. Nessuna installazione o verifica Nuvio è giustificata
da queste evidenze; la successiva lettura inventario predisposta sopra risolve
solo la domanda sullo stato dopo lo Store.
Il test BlobService ha chiuso un'ipotesi concreta; il servizio ospitato ha un
indirizzo confermato ma è indisponibile nel test e manca comunque la strada
launcher accettata. Non chiedere all'utente di contattare VIDAA, diventare
partner, usare MSX o ripetere i probe respinti. Per riaprire la ricerca serve
un nuovo importatore/procedura pubblica autorizzata, o un servizio Nuvio
funzionante con percorso launcher accettato; nessuna modifica al bundle
può sostituire tale prerequisito.

## Provenienza e stato Git

- Letti interamente `AI_CONTEXT.md`, `LATEST_RESPONSE_AND_NEXT_CHAT.md` e
  `README.md` prima di modificare. Nessun `AGENTS.md` trovato nelle due repo
  o nei percorsi antenati controllati.
- Sidee all'inizio: `main`, HEAD `89acbe5ada4ae221773fd426c65918bd786dbe6e`.
  Unica modifica locale: nuovo `control/request.json` già in staging, con
  richieste disattivate. Preservato e escluso dal commit della valutazione.
- Il fetch ha trovato cinque commit successivi; allineamento fast-forward a
  `7c4700ea5e239925ad4531191e0de92124cfc09a`, senza avviare il server.
  Letti anche il nuovo handoff, la configurazione di auto-capture e il nuovo
  passaggio di consegne. Il vecchio piano non è stato eseguito.
- Nuvio: `D:\nuvio\nuviotvsmart`, `main`, HEAD
  `1f1ad284a292c06b0ed6b045dd1e1f3177666d1b`, working tree pulito.
  Nessuna modifica o ricostruzione degli artefatti Nuvio in questa fase.

## Ricerca successiva richiesta dall'utente — 50E77NQ

L'utente ha chiesto di cercare autonomamente un modo, senza delegare la ricerca
al supporto. Sono stati controllati altri percorsi pubblici e il modello preciso.
L'esito resta: nessun meccanismo pronto e dimostrato per tutti i requisiti.

### Nuvio: distribuzione e risposta dei maintainer

- L'API GitHub ufficiale conferma issue #790 chiusa con `state_reason:not_planned`
  dal `2026-09-19T17:18:38Z`, aggiornata il 25 settembre. L'indice search conserva
  ancora uno snapshot “Open”: per lo stato vale l'API corrente.
- Il [commento del 25 settembre](https://github.com/NuvioMedia/NuvioTVSmart/issues/790#issuecomment-5839576551)
  classifica PR #1007 come registrazione di una UI ospitata; la strada nativa
  richiede integrazione e distribuzione confermate con VIDAA. Non fornisce
  un nuovo sideload locale.
- [PR #1007](https://github.com/NuvioMedia/NuvioTVSmart/pull/1007), autore
  Empi9245: API corrente `closed`, `merged:false`, chiusa
  `2026-09-25T21:02:43Z`; head `00cfecaa02e22d903b2d004ced58150527eda39f`
  su `vidaa-upstream-1.2.0`. La pagina indicizzata “Open” è obsoleta.
- Il [confronto dei due commit](https://github.com/Empi9245/nuviotvsmart/compare/1f1ad284a292c06b0ed6b045dd1e1f3177666d1b...00cfecaa02e22d903b2d004ced58150527eda39f)
  mostra un commit successivo al checkout locale: isolamento VIDAA e correzione
  precache a `css/bundle.css`, senza un diverso meccanismo di importazione.
  Esaminato il diff di build/packager/SW; nessun merge nella repo Nuvio.
  Le incongruenze SW descritte sotto riguardano il checkout locale `1f1ad284`.
- [Release ufficiale 1.2.1](https://github.com/NuvioMedia/NuvioTVSmart/releases/tag/1.2.1),
  pubblicata `2026-09-28T16:36:35Z`: WGT Tizen, IPK webOS e installer desktop;
  nessun asset VIDAA. Controllate anche 1.2.0 e 1.1.9, stesso limite.

### VIDAA e strumenti alternativi

- La [FAQ ufficiale partner in turco](https://www.vidaa.com/is-ortaklari/)
  è ancora accessibile: supporta HTML5 e native Linux, stima 12–18 mesi per
  integrazione nativa, offre strumenti/dispositivi ai partner e condivide
  specifiche dopo NDA. Non contiene una procedura consumer di importazione
  locale per Q0707 senza devkit. Questo impedisce di dire “VIDAA non supporta
  mai app native”, ma non sblocca il port corrente.
- [NAGRAVISION CONNECT SDK](https://docs.nagra.vision/connect-player-sdk-5-for-browsers/5.28.x/Default/smart-tv-apps)
  descrive le proprie app VIDAA nello Store come HTML5 ospitate, distinguendole
  dagli app payload di altre piattaforme. Conferma il modello di distribuzione
  ordinario per quel SDK; non esclude package nativi o componenti di sistema.
- [trialuser/vidaa-appstore](https://github.com/trialuser/vidaa-appstore) e
  [vidaa-custom-app](https://github.com/arashbehmand/vidaa-custom-app) configurano
  URL delle app. “Local” o “container” si riferisce al server sul PC/Docker,
  non a un contenitore installato nella TV che importi risorse.
- [Vidaa Edge](https://github.com/weinzii/vidaa-edge) descrive due vie:
  registrazione tramite API e scrittura del registro applicazioni. Non documenta
  un bundle Nuvio conservato localmente. Non sono stati eseguiti questi metodi
  né tentativi contro il rifiuto AppConfig già osservato.
- [NoobyGains/stremio-vidaa-tv](https://github.com/NoobyGains/stremio-vidaa-tv)
  dichiara esplicitamente bookmark/service-worker e installer launcher
  non affidabile sui firmware recenti. Non è nuova evidenza di package locale;
  nessun test ripetuto sulla TV.

### Contenitore MSX: supporto confermato, importazione non dimostrata

La [tabella ufficiale MSX](https://msx.benzac.de/info/?tab=PlatformSupport)
include VIDAA U6+, versione elencata 0.1.167. Quindi non è corretto trattare
MSX come piattaforma VIDAA non supportata. La presenza nello Store della
specifica TV/regione resta non verificata; era assente nell'inventario salvato.

Sono state esaminate anche [Setup Start Parameter](https://msx.benzac.de/wiki/index.php?title=Setup_Start_Parameter),
[Start Object](https://msx.benzac.de/wiki/index.php?title=Start_Object),
[Plugin API Reference](https://msx.benzac.de/wiki/index.php?title=Plugin_API_Reference)
e [Tips & Tricks](https://msx.benzac.de/wiki/index.php?title=Tips_%26_Tricks).
Il setup documenta JSON ospitato e parametri conservati; `TVXServices.storage`
è un wrapper di localStorage. `TVXBlobService` espone load/execute di blob,
ma la pagina non documenta importazione e rilancio persistenti di app dopo
riavvio. Questi nomi non bastano a promuovere MSX a soluzione locale.
Non è stato costruito un loader basato su API presunte, data URL non documentati
o cache. Per riaprire questa strada serve una funzione documentata che conservi
ed esegua le risorse proprie, con input utile, e poi la prova sulla TV.

### Manuali del modello e piste USB/hospitality

Dalla [pagina ufficiale 50E77NQ](https://it.hisense.com/prodotti/tv/tv-hi-qled/TV-SET-50E77NQ-HSN/p/000000000020014013)
sono stati scaricati i due PDF collegati. I download sono riusciti via HTTPS
diretto anche se il lettore web restituiva “Cache miss”. Ispezionate visivamente
le pagine introduttive pertinenti, perché i PDF sono scansioni senza testo.

| Fonte ufficiale | Identificazione | Limite |
| --- | --- | --- |
| [Italiano](https://partners.gorenje.com/fts/GetDigitDoc.aspx?docName=24081513470448382.pdf&jezik=it&sifra=20014013&tipVsebine=1) | 18 pagine, SHA256 `00e2431f7c956f84f67534b5b9aa40fba4102043f5c8091c561e8b0dd88ffc50` | guida hardware/sicurezza; rinvia all'E-Manual integrato per funzioni software |
| [Inglese](https://partners.gorenje.com/fts/GetDigitDoc.aspx?docName=b+1401910+es-a23441m-1+um+hisense+43-50-55-65-75-85e70levs_en.pdf&jezik=en&sifra=20014013&tipVsebine=1) | 20 pagine, SHA256 `dba46c807fd92e7b65481a26a1c4c16169b0f96d30dfbe9e0147f5c6c3da3cff` | stesso rinvio all'E-Manual; non è documentazione aggiornata specifica di Q0707 |

Non dedurre da queste guide l'assenza universale di un importatore USB. Non è
stata trovata una procedura di installazione locale utilizzabile. Il manuale
[Hisense B2B](https://www.hisense-b2b.com/Attachment/DownloadFile?downloadId=20)
con “Custom App”/copia file descrive invece un display Android: Android Launcher
e Android Version sono espliciti. Non è applicabile alla 50E77NQ VIDAA.
Clonazione canali/impostazioni o aggiornamento firmware non dimostrano import
di risorse HTML/JS/CSS. Nessun cambio hotel/service mode o firmware effettuato.

### Stato e arresto della ricerca corrente

Report locale e remoto invariati: il ramo report resta `f8dee5d` del 29 settembre.
Nessun nuovo risultato TV. La ricerca documentale non ha trovato il prerequisito
per un'implementazione locale. I cinque criteri di accettazione rimangono tutti
non verificati. Non presentare questa ricerca come installazione riuscita.
Per proseguire serve nuova evidenza tecnica autorizzata (formato/procedura
locale, importatore persistente documentato, o distribuzione del produttore
che soddisfi esplicitamente l'obiettivo). Altri probe identici non la sostituiscono.

## Report verificati

| Evidenza | Data e contenuto | Limite |
| --- | --- | --- |
| Ultimo locale: `reports/sidee-session-20260929-194224-f686.json` | aggiornato `2026-09-29T19:10:18Z` = 21:10:18 italiane; build `app-5dbeec3fbd21`, `buildMatch:true`; solo discovery/timeline DNS, `targetDomainHit:false` | nessun `fullNetworkCapture`, nessuna verifica installazione o risorse locali |
| Ultimo remoto: `origin/sidee-reports:reports/latest.json` | commit `f8dee5d5ced6fde8b7d936a92bec45bd423643fb`, 29 settembre 21:09:38 +0200; stessa sessione/build, `updatedAt:2026-09-29T19:09:35Z` | copia remota 43 secondi più vecchia del locale; non confondere commit report con commit applicazione |
| Build dell'ultimo report | digest ricostruito sui quattro file usati da `client_build_id()`, con CRLF del checkout Windows: corrisponde a `f5b5a9b8d593081487793e2020e122887c7e386b` e al successivo commit solo documenti `89acbe5` | il report non contiene un campo Git HEAD; il digest non distingue commit con identico codice. Non documenta l'auto-capture aggiunta in `c895f314` |
| Ultimo browser: `sidee-session-20260929-191916-046b.json` | `updatedAt:2026-09-29T17:42:57.637Z`, stessa build; `hiWebOsFrameAvailable:false`, `keyboardAvailable:false`, routing non tentato, `success:false`, zero eventi; install automatico `SKIPPED/INSTALL_API_UNAVAILABLE` | vale per il browser raw-IP, non prova la navigazione Nuvio in un'app autorizzata |
| Cattura utile: `sidee-session-20260929-173911-7b2f.json` | PCAPNG, 384 IPv4, 382 record HTTPS, 89.666 byte; `FILTERED_FLOW_VISIBLE_AFTER_NAT`; rianalisi `2026-09-29T16:07:33Z` | rete HTTPS già visibile; path/body TLS restano cifrati. Assenza di SNI Duplecast o di un flusso grande non esclude cache/riuso connessioni o piccoli download |
| Registro originale: `sidee-session-20260926-153038-1083.json` | `installedAppMetadata.appInfoDeepDump.records`: Duplecast ID 1876, URL e StartCommand `http://vidaa.duplecast.com/`, `appInfo.packaged:0`, `appBundle:""`, `configUrl:""`, `configUrlDownload:0` | snapshot del 26 settembre, precedente alla reinstallazione; nessuna misura corrente dei file conservati dopo il nuovo “Installa” |

La stessa cattura salvata esiste ancora sotto
`captures/sidee-net-20260929-173911/`. Non è stata rianalizzata nuovamente:
non serve per distinguere i tre modelli di distribuzione.

## 1. Pacchetto Nuvio installato e conservato sulla TV

**Evidenze disponibili.** Il runtime osservato espone `vowOS.store`,
`getInstalledPkgs`, `installApp` e `sendPkgmgrRequest`. Il contesto documenta
18 package reali, compreso un package `web`. Il wrapper, dopo installazione
riuscita, costruisce `file:///APPS/pkgs/<pkgName>/index.html` e poi registra
l'app con `Hisense_installApp`: conservazione fisica e launcher sono due fasi.
I package di sistema elencati non coincidono con le tre web app del registro;
nessuno stager/downloader pubblico è stato identificato. Le letture del
tvbrowser e le scansioni già esaurite non vanno ripetute.

Nel port Nuvio `scripts/package-vidaa.mjs` copia `dist` e `installer` e crea
uno ZIP tramite JSZip. Non genera un manifest package VIDAA dimostrato, una
firma VIDAA o una procedura di importazione accettata dalla Q0707. Il
`manifest.json` è un manifest web con `start_url` e `display:fullscreen`.
`appinfo.json` è metadata del progetto, non una prova di packaging VIDAA.
Al momento `dist/nuvio-vidaa.zip` e `dist/vidaa` non sono presenti; il codice
del packager è stato esaminato, non è stata dichiarata riuscita una build.

**Da dimostrare.** Formato autorizzato, origine/staging, accettazione di un
package di proprietà dell'utente con ID proprio, registrazione launcher e
conservazione dei file. Le autorizzazioni della normale pagina hanno già
respinto registrazione/write con AppConfig 503. Nessun tentativo di aggirarle.

**Dipendenze.** Una vera copia locale avrebbe bisogno del PC solo per preparare
o trasferire il package. Nell'uso normale nessun hosting UI, PC o DNS
personalizzato; cache non necessaria alla presenza dei file. Contenuti/account
possono continuare a usare Internet.

**Prossimo test decisivo.** Prima individuare in fonti pubbliche una procedura
autorizzata applicabile a Q0707 per distribuire un'app propria, conservata
localmente, senza devkit o percorso partner. Solo se esiste: importare un'app minima con ID proprio,
verificare risorse in storage applicativo autorizzato e apertura dal launcher
dopo riavvio con fonte di trasferimento spenta; poi usare il bundle Nuvio.
Il contatto VIDAA e il percorso partner sono esclusi dall'utente.

**Abbandono.** Se è disponibile solo URL hosting, oppure sono necessari devkit,
debug firmware, permessi/firme non ottenibili legittimamente o manipolazione
di un package altrui, questa strada termina per lo scope corrente. Lo ZIP
generico non giustifica un test `pkgmgr install` con un nome inventato.

## 2. Registrazione nel launcher di una app ospitata

**Evidenze disponibili.** SmartOne, Stremio Lite e Duplecast hanno URL remoti
nel registro. Duplecast è esplicitamente non packaged nello snapshot osservato.
La sostituzione temporanea della risposta HTTP negli esperimenti storici ha
fatto eseguire Sidee nel contesto nativo Duplecast: dimostra caricamento remoto
e identità launcher, non copia persistente di Nuvio.

`installer/index.html` Nuvio costruisce `APP_URL` dall'origin corrente e chiama
`Hisense_installApp` con quel URL. Non trasmette lo ZIP o i byte di HTML/JS/CSS
alla TV. Il server Python serve i file dal PC. Il callback `0` mostra ancora
"Installation successful!": falso criterio di successo già smentito sulla TV.
Se l'origin è `https://vidaahub.com`, ripristinare DNS automatico non trasferisce
l'interfaccia e non conserva l'associazione di quel dominio al PC.

**Da dimostrare.** Per la reinstallazione Duplecast del 29 settembre non c'è
un confronto prima/dopo di risorse applicative persistenti. La classificazione
meglio sostenuta è **registrazione di app ospitata**, con eventuale cache non
misurata. Non è provato che “Installa” copi un package locale o soltanto e
esclusivamente metadata; potrebbero essere memorizzati anche icone/config/cache.
DNS `files.duplecast.com` non identifica il tipo di file trasferito.

Per Nuvio manca una registrazione consentita su questa TV. Il successivo
controllo ha identificato un endpoint ospitato ufficiale, `web.nuvioapp.space`,
ma ha ottenuto HTTP 522; funzionamento e compatibilità VIDAA non verificati.
Il repository documenta Tizen/webOS, non una distribuzione VIDAA.

**Dipendenze.** Hosting UI permanente. Con il server attuale servono PC e
potenzialmente DNS personalizzato; un host pubblico gestito dall'utente
continua a essere self-hosting. Un servizio gestito da Nuvio/VIDAA potrebbe
eliminare PC e hosting a carico dell'utente, ma resta un modello remoto,
condizionale e oggi non verificato. La cache non sostituisce il servizio.

**Prossimo test decisivo.** Per chiarire Duplecast, usare un'eventuale futura
installazione ordinaria per acquisire metadata/storage applicativo prima/dopo
tramite strumenti documentati; riavviare e rendere irraggiungibile la sola
origine UI mentre i servizi contenuto restano raggiungibili. Il fallimento
dimostra la dipendenza; un successo isolato può ancora essere cache e richiede
provenienza/package/versione dei file conservati. Non reinstallare ora per
ottenere soltanto altri SNI/volumi TLS.

Per far avanzare Nuvio serve prima un URL UI ufficialmente gestito e una
registrazione launcher consentita, poi l'intera verifica TV. Sono precondizioni
non soddisfatte, non nuovi probe da eseguire alla cieca.

**Abbandono.** Scartare per l'obiettivo finale se richiede hosting a carico
dell'utente, PC/DNS durante uso normale, solo cache o registrazione vietata.
Non adottare implicitamente una web app ospitata come sostituto dell'obiettivo.

## 3. Contenitore con risorse Nuvio locali e persistenti

**Evidenze disponibili.** Duplecast e SmartOne già osservati sono player IPTV;
la loro documentazione pubblica descrive playlist M3U/Xtream e formati media,
non importazione di app HTML/JS/CSS proprie in storage applicativo persistente.
L'identità nativa non implica una funzione di importazione o un permesso write.

Media Station X ha API documentate per contenuti, link e plugin; non compare
nell'inventario di 61 app del 26 settembre, quindi non è dimostrato installato
qui. L'utente ha poi confermato che è disponibile nello Store, ma non vuole
usarlo: escluso dalla soluzione. La documentazione di
setup richiede un server HTTP per i JSON; l'Interaction Plugin è una pagina
in iframe di background che non riceve input. Queste funzioni non dimostrano
un contenitore capace di conservare e far usare tutta l'interfaccia Nuvio.
JSON inline e configurazioni persistenti non equivalgono a importare il bundle.

**Da dimostrare.** Nome/versione di un contenitore disponibile sulla Q0707,
funzione autorizzata di importazione di risorse proprie, storage non dipendente
da cache, esecuzione di JavaScript e controllo completo dei tasti/player.

**Dipendenze.** Se l'importazione è reale, PC solo per trasferimento iniziale,
nessun host UI o DNS personalizzato nell'uso normale. Se apre un link remoto,
serve hosting come nella strada 2. Se persiste solo un URL/playlist/cache,
il requisito delle risorse locali resta insoddisfatto.

**Prossimo test decisivo.** Ammissibile solo dopo documentazione di una funzione
di importazione: caricare una piccola app propria con JS/CSS e stato di prova,
riavviare la TV e la app dal launcher, togliere la fonte di trasferimento,
verificare frecce/OK/Indietro e file/stato conservati; poi integrare Nuvio.

**Abbandono.** Scartare un contenitore se accetta solo playlist/link, dipende
da URL server/cache, non conserva i file, non espone input utile o richiede
sostituzione del contenuto/package di un'app terza, firme/permission bypass.
Duplecast e SmartOne non superano oggi questa precondizione documentale.

## Port, persistenza e verifica reale

Il port contiene mapping D-pad/OK e Back (8/461/10009/27), viewport VIDAA,
adattamento della tastiera e player HTML5. Questi sono fatti di codice;
non provano input DOM ricevuto, playback, lifecycle o avvio locale sulla Q0707.
`launchVidaaNativePlayer` invia un messaggio OMI e ritorna true dopo il dispatch,
senza ACK: non è una verifica di riproduzione.

Lo stato account/preferenze usa localStorage; è distinto dalla conservazione
dei file dell'interfaccia. Il service worker ha inoltre una lista precache
incoerente con la build: `css/base.css`, `layout.css`, `components.css`,
`themes.css` contro la sola `css/bundle.css`, e `res/icon.png` contro l'icona
in `assets/images`. `cache.addAll` fallisce con risposte non riuscite e il catch
non dimostra caching riuscito. Il normale HTTP su IP LAN non fornisce il secure context necessario
al service worker. Non è stato corretto il SW come presunta soluzione: anche
una cache funzionante non dimostrerebbe l'installazione richiesta.

| Criterio di accettazione Nuvio | Stato al 2026-09-30 |
| --- | --- |
| Apertura dal launcher | NON VERIFICATA per Nuvio |
| Frecce, OK, Indietro senza cursore | NON VERIFICATI per Nuvio in un'app; browser Sidee ha zero eventi |
| Riapertura dopo chiusura e vero riavvio | NON VERIFICATA |
| Avvio con Sidee e host locale UI spenti, DNS automatico | NON VERIFICATO |
| UI caricata e contenuto di prova autorizzato riprodotto | NON VERIFICATI in tale configurazione |

Quando una strada supera la precondizione documentale, verificare questi cinque
criteri sulla TV, annotando versione/build, launcher utilizzato, riavvio reale,
stato dei server, origine effettiva dei file e contenuto di prova autorizzato.
Per le strade locali la fonte dei file deve essere storage applicativo
autorizzato, non soltanto un avvio riuscito dalla cache. Non rimuovere dati
account o app altrui per provare la persistenza.

## Fonti pubbliche controllate il 2026-09-30

- [MDN Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
  e [Cache.addAll](https://developer.mozilla.org/en-US/docs/Web/API/Cache/addAll):
  secure context e fallimento per risposte non 2xx; non sono prove dello storage
  applicativo della TV.
- [Nuvio ufficiale](https://github.com/NuvioMedia/NuvioTVSmart): README corrente
  documenta Tizen/webOS. Confermato nella pagina consultata; non è un inventario
  universale di ogni collaborazione privata o progetto VIDAA.
- [V/VIDAA Content Partners](https://v-home.com/csp/): onboarding e infrastruttura
  hosting/CDN per partner. Conferma un canale ufficiale, non certifica un
  importatore locale per Q0707 o accettazione del port Nuvio.
- [VIDAA Privacy Policy 2026](https://www.vidaa.com/privacy-policy-2026/): il
  Partner Portal è su invito. Non dedurre che la registrazione al generico sito
  V conceda accesso sviluppo o permessi TV.
- [Duplecast features](https://www.duplecast.com/features) e
  [How it works](https://duplecast.com/how-it-works): funzioni di player/playlist;
  nessuna importazione di app locali documentata nelle pagine controllate.
- [SmartOne](https://smartone-iptv.com/): player e gestione playlist/account;
  nessuna importazione di app locali documentata nella pagina controllata.
- [MSX Setup Precondition](https://msx.benzac.de/wiki/index.php?title=Setup_Precondition),
  [Interaction Plugin](https://msx.benzac.de/wiki/index.php?title=Interaction_Plugin),
  [Actions](https://msx.benzac.de/wiki/index.php?title=Actions): server HTTP,
  iframe senza input, link/JSON inline. Capacità documentate, compatibilità
  e storage locale sulla TV specifica non provati.
- La guida storica VIDAA `WebApp_Development_Guide_for_VIDAA.pdf` su
  `www.vidaa.com/wp-content/uploads/2020/12/` compare ancora nell'indice search
  con la descrizione delle hosted app, ma l'apertura diretta ha restituito 404.
  Non è stata usata come manuale corrente di sideload. Anche `/partners/` è 404;
  la homepage ufficiale rimanda ora a `v-home.com`.

Non serve ripetere la ricerca su callback 0, V2, origin/DNS, identifier,
HSPDK, path tvbrowser, staging JS, MITM Store respinto o visibilità HTTPS/NAT.
Una nuova cattura ha senso solo con una domanda discriminante e una evidenza
applicativa documentata che possa essere correlata; SNI/byte da soli non
identificano un package installato.
