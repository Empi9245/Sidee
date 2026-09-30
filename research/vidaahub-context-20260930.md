# vidaahub.com: contesto, API e autorizzazione

Indagine del **30 settembre 2026**, Europe/Rome. Target: Hisense **50E77NQ**,
`V0000.09.60A.Q0707`, VIDAA U09.60, MTK9603, Odin/Chromium 111.
Letture obbligatorie completate prima di modifiche/verifiche. Base Sidee:
`bdd2c2d91ae1fc1e3cec6186c9b20bc49bff4bca`, `main`; base Nuvio:
`1f1ad284a292c06b0ed6b045dd1e1f3177666d1b`, `main`.

## Risposta alla domanda prioritaria

Esiste una differenza pubblicamente descritta fra le vecchie procedure e le
generazioni successive: un fornitore distingue VIDAA 2/3/4 da VIDAA 5+, e il
maintainer di vidaa-edge riferisce che da v9 non serve più la riscrittura DNS.
Questo riguarda l'accesso al bridge, **non dimostra un nuovo diritto di scrittura**.
Sulla TV target il vecchio contesto vidaahub esponeva già le API install legacy
e V2, ma entrambe fallivano internamente con AppConfig 503. Due contesti di app
native respingevano ugualmente la scrittura, pur con identità presente.

Non è stata trovata una specifica pubblica Q0707 che stabilisca un nuovo contesto
autorizzato, un'API sostitutiva di importazione o una nuova regola di autorizzazione
per una propria app. Nessun indirizzo alternativo è dimostrato capace di concedere
quei permessi. Le segnalazioni 09.60 contemporanee confermano che esposizione e
autorizzazione possono divergere; non identificano la prima versione che cambiò
le regole. Mancano vecchio/nuovo firmware misurati con lo stesso codice e contesto.

La domanda sulle risorse conservate sulla TV rimane separata: nessun nuovo byte
di app è stato letto. L'inventario del 30 settembre non risolve quella domanda.
Nessuno dei cinque criteri Nuvio è stato verificato in questa sessione.

## Confronto dei report già salvati — nessuna nuova chiamata TV

[Confronto JSON](vidaa-context-comparison-20260930.json) contiene nomi, SHA256,
dimensioni, timestamp, build e risultati selezionati dei sei report reali.
Si rigenera offline con `python research/compare-vidaa-contexts.py`; lo script
non usa rete, TV o Git e non esporta identificatori nativi, credenziali o registro
completo. I report sorgente restano locali e ignorati da Git.

| Data UTC / report | Contesto | Build registrata | API disponibili / risultato | Permesso osservato | Risorse locali |
| --- | --- | --- | --- | --- | --- |
| 25/09 18:25, `195421-ff60` | `https://vidaahub.com` | non registrata | install legacy/V2, elenco app, HiUtils e OMI presenti; callback 0 | entrambe respinte, return false, `ret:false`, AppConfig 503 | nessuna prova di copia Nuvio |
| 26/09 13:08, `150815-b6a2` | HTTP LAN | `app-7c6c95bcb6e0`, match true | campi capability non registrati nel riepilogo; no-op storico | false/503, readback identico | nessuna prova di copia |
| 26/09 13:30–13:31, `153038-1083` | `https://vidaahub.com` | `app-05842432cb14`, match true | scrittura no-op e baseline storiche | WRITE_DENIED, false/503, readback identico | Duplecast precedente alla reinstallazione: URL remoto, packaged 0, appBundle vuoto |
| 26/09 14:09, `160944-2811` | app nativa Duplecast | `app-05842432cb14`, match true | HiUtils/vow service/context presenti; install legacy/V2 e FileRead/Write assenti; identità nativa e SupportAppConfig presenti | no-op WRITE_DENIED, false/503, readback identico | identità nativa non prova file Nuvio |
| 26/09 14:12, `161255-410f` | app nativa SmartOne | `app-05842432cb14`, match true | medesima distinzione di capability e identità | no-op WRITE_DENIED, false/503, readback identico | nessuna lettura di risorse |
| 30/09 12:09, `post-store-120901-112525` | HTTP LAN, insecure | build non registrata | elenco app UNAVAILABLE; package READ_OK, 18 componenti di sistema | install/write non eseguiti | tvbrowser web locale; non inventario completo Store o risorse di altre app |

Le build annotate provengono dai report; i loro commit di esecuzione non sono
registrati e non vengono inventati. La base Git di questa ricerca non è il
commit che generò quei report. Build uguale fra vidaahub e app native non significa
bootstrap/contesto identico; build LAN precedente diversa. Non è un A/B che
isoli il solo hostname, né un confronto tra firmware. I campi mancanti significano
non registrato, non API assente o autorizzazione negata.

Ultimo inventario: timestamp pagina `2026-09-30T12:09:05.471Z`; campo ricezione
`2026-09-30T12:09:01.111526+00:00`, equivalente a 14:09:01.111526 Europe/Rome.
Entrambe le copie: 4281 byte, SHA256
`78b8bc5564464bc9d17b823b482d6b3d94cebfe7d22f31e094da21229841ab4f`.
Il lieve ordine inverso dei due orologi non documenta un'altra sessione.
Provenienza completa in [post-store-result-20260930.md](post-store-result-20260930.md).

## Fonti pubbliche primarie ricontrollate

### vidaa-edge: documentazione precedente e segnalazioni recenti

[Issue 30](https://github.com/weinzii/vidaa-edge/issues/30) ancora aperta alla
verifica, cinque commenti, creata `2026-06-10T08:59:50Z`, ultimo aggiornamento
`2026-09-09T22:41:42Z`. Un 85U8Q `V0000.09.60F.Q0528` segnala API disponibili
con AppConfig negato. Commenti riportano problemi analoghi su Q0516 e Q0602;
quest'ultimo riferisce 104 funzioni caricate e assenza di Hisense_FileRead.
Sono altri dispositivi/build, non un test sostitutivo sulla 50E77NQ.

Il [commento del maintainer](https://github.com/weinzii/vidaa-edge/issues/30#issuecomment-5384773871)
riferisce che da v9 non occorre riscrivere DNS. Il
[commento Q0602](https://github.com/weinzii/vidaa-edge/issues/30#issuecomment-5609694627)
separa il caricamento delle funzioni dal fallimento AppConfig. Non sono una
concessione ufficiale di permessi né una correzione verificata su Q0707.

La [README alla revisione controllata](https://github.com/weinzii/vidaa-edge/blob/94c3134911cbd4b813eea1f88c56819c0981518b/README.md)
mantiene le vecchie istruzioni DNS e registrazione URL. Ultimo commit trovato sul
default branch: `94c3134911cbd4b813eea1f88c56819c0981518b`,
`2025-12-03T21:02:53Z`; blob README `a477e6b3ef5cedde2f1fdfffb9f0479fa50df192`.
Non c'è qui un aggiornamento di codice 2026 che provi una nuova autorizzazione.
I percorsi di documentazione citati da indici secondari erano obsoleti: uno
restituisce 404 nel repository. Non usarli come specifica corrente.

### TVOЁ: diverso ingresso pubblicato, ma stessa registrazione URL

La [pagina del fornitore](https://vidaa.tvoe.app/) distingue vecchie generazioni
VIDAA 2/3/4 e VIDAA 5+. Descrive l'installazione della propria app, non autorizza
importazioni arbitrarie. È una fonte primaria del fornitore, non una specifica VIDAA.
Non abbiamo eseguito le sue procedure DNS o aperto questa pagina sulla TV.

Letture HTTPS dal PC del 30 settembre, senza eseguire il bundle:

- HTML: HTTP 200, 600 byte, SHA256
  `540e81ea737049016dea7adebab609996b19a5032496a00ac707f23066665f9d`.
- [Bundle referenziato dall'HTML](https://vidaa.tvoe.app/static/js/bundle.js):
  HTTP 200, 1.870.790 byte, SHA256
  `cec7b51ddd5adde4c09970d924ec0a1b95930553bfd83d933e7b1db397dd3277`.

Nel codice esaminato `installNewApp` usa `Hisense_installApp` con URL
`https://tv.tvoe.live?installed=vidaa`; il ramo callback 0 mostra successo.
Il controllo iniziale considera HiUtils per 9+, ma la routine nuova richiede
Hisense_installApp. La rilevazione del bridge non verifica il permesso.
Non c'è trasferimento di package in questa routine, né una prova Q0707 o un
contratto che conceda a Nuvio identici diritti. Questo documento distingue una
procedura pubblicata dalla sua effettiva riuscita: callback 0 resta insufficiente.

### Fonti ufficiali e documentazione per sviluppatori

Il vecchio [WebApp Development Guide](https://www.vidaa.com/wp-content/uploads/2020/12/WebApp_Development_Guide_for_VIDAA.pdf)
restituisce ancora HTTP 404. Non è disponibile come specifica corrente Q0707.
La [FAQ HomeOS](https://v-home.com/faq/) descrive la continuità della piattaforma
nella nuova denominazione; non documenta una migrazione di API/AppConfig o una
nuova origine privilegiata. Il [catalogo web VIDAA](https://apps.vidaa.com/web/home)
non ha fornito un importatore pubblico di proprie app nelle informazioni lette.
L'assenza nelle pagine lette non esclude funzioni non pubblicate.

La [pagina debug Trillboards](https://trillboards.com/screen-apps/debug/) rimanda
ancora a devkit/vidaahub per testare API proprietarie. Nessun download o uso del
devkit: è escluso. Non è un nuovo ingresso consumer autorizzato su Q0707.

## Radice vidaahub.com: il PC non è un osservatore neutro

Il file hosts del PC contiene **`192.168.1.8 vidaahub.com`**. È preesistente e
non è stato modificato. La risoluzione ordinaria sul PC restituisce quell'IP e
il GET HTTPS è scaduto: quel timeout **non prova** lo stato del sito pubblico.
Nessuna riscrittura DNS/TLS è stata avviata per questa ricerca.

Letture pubbliche DNS-over-HTTPS separate, senza cambiare il resolver del PC:

| Query Google Public DNS | HTTP / bytes | Risposta | SHA256 corpo |
| --- | --- | --- | --- |
| [A](https://dns.google/resolve?name=vidaahub.com&type=A) | 200 / 298 | Status 0, nessuna Answer, SOA AWS nell'Authority | `2f6498d8e0cdadeb0e83407587e31523f22f304cc0605f92cf02b1dc8ddeb2c5` |
| [AAAA](https://dns.google/resolve?name=vidaahub.com&type=AAAA) | 200 / 257 | Status 0, nessuna Answer, SOA AWS nell'Authority | `50015c78c4b7b2be9da8653b49287f150bde237ea07cfe19620e01c697062956` |

È NODATA in quel resolver/momento, non NXDOMAIN né una prova universale o di
whitelist. La radice non è dunque dimostrata un portale pubblico oggi raggiungibile
per importare Nuvio. I sottodomini Store regionali già osservati hanno ruoli
distinti: non vengono proposti come origini da impersonare o provare per ottenere
permessi. Nessuna enumerazione di host privilegiati è stata effettuata.

## Strade concrete e prossimo test decisivo

| Strada | Evidenza | Prerequisito mancante / dipendenza | Test che decide | Quando abbandonare |
| --- | --- | --- | --- | --- |
| Package/sideload proprio | ZIP Nuvio web; nessun import Q0707 dimostrato | procedura pubblica autorizzata, formato e storage documentati; UI locale | app minima propria, launcher/D-pad, riavvio reale PC/Sidee/UI host spenti, contenuto autorizzato | se richiede bypass, devkit/partner o serve ancora l'UI dal PC |
| Contenitore persistente | identità Store e tvbrowser locale, ma non risorse Nuvio | import di risorse proprie consentito e storage persistente; MSX escluso | stessi criteri, includendo provenienza/file versione riconoscibile | se conserva soltanto URL/cache/sessione o dipende da percorso escluso |
| UI gestita da un fornitore | procedure URL pubblicate per altre app; port Nuvio hosted già documentato | servizio Nuvio utilizzabile, distribuzione launcher autorizzata, disponibilità del fornitore | lancio/telecomando/riavvio PC spento e playback autorizzato, dipendenza esterna dichiarata | se launcher negato, endpoint indisponibile o richiede hosting dell'utente |

Nessuna candidata supera ora il prerequisito per una prova di vera installazione
Nuvio. Il prossimo test decisivo **non è un altro snapshot IP**: serve prima una
procedura documentata per la propria app sul firmware target. Con quel fatto
nuovo si prepara e importa un'app minima con ID proprio e versione riconoscibile;
poi si misura davvero launcher, telecomando, riavvio con host spenti e playback.
Se emergesse invece una specifica di contesto/API aggiornata, verificarne prima
applicabilità, autorizzazioni e storage: il solo nome di un altro dominio non basta.
Senza tali evidenze non c'è un prossimo tentativo TV giustificato nei vincoli
attuali. Non si conclude un'impossibilità universale.

## Lavoro realizzato e verifica

Nuvio: corretti i falsi messaggi di successo dell'installer e le promesse del
packager; aggiunto `D:\nuvio\nuviotvsmart\VIDAA_STATUS.md`. Nessun nuovo SDK,
probe, build, ZIP o tentativo TV. Logica di packaging invariata. Verifica off-TV:
controllo sintassi packager; esecuzione isolata dello script installer con DOM/API
fittizi per callback 0, errore, API assente e rimozione; controllo formattazione
dei due sorgenti. Non prova permessi reali.

Sidee: confronto offline dei sei report, nessun cambiamento ai servizi/probe TV.
Ricevitore isolato ancora presente alla verifica (PID 5676, LAN :8080, /status
200 e stesso report). HTTPS già risolto: 382 record dopo NAT, non ripetuto.
`control/request.json` dell'utente resta in staging, escluso dal commit.
