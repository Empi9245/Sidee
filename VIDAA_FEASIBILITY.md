# Nuvio sulla Hisense VIDAA 9: valutazione di fattibilità

Verifica: 2026-09-30, Europe/Rome. TV: firmware `V0000.09.60A.Q0707`,
OS `U09.60`, MTK9603, Odin/Chromium 111.

## Esito

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

**Prossimo test decisivo.** Prima ottenere da VIDAA una procedura documentata
applicabile a Q0707 per distribuire un'app propria, conservata localmente,
senza devkit. Solo se esiste: importare un'app minima con ID proprio,
verificare risorse in storage applicativo autorizzato e apertura dal launcher
dopo riavvio con fonte di trasferimento spenta; poi usare il bundle Nuvio.
Richiedere questa informazione tramite il canale ufficiale è un possibile
passo umano, non un messaggio inviato da Sidee o da questa chat.

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

Per Nuvio manca sia una registrazione consentita su questa TV sia un endpoint
UI VIDAA gestito dal produttore verificato. Il repository ufficiale consultato
documenta Tizen/webOS, non una distribuzione VIDAA.

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
qui né disponibile nello Store italiano di questa TV. La documentazione di
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
