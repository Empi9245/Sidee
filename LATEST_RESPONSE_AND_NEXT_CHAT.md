# Sidee — risposta aggiornata + prossima chat

Data: 2026-09-26

## Stato reale da cui partire

Repository:

`Empi9245/Sidee`

Branch:

`main`

HEAD verificato all'inizio di questa analisi:

`e9c32619aca2cfa4ec6db0da1d5f444cc712eee8`

commit:

`docs: separate pkgmgr packages from web AppInfo registry`

Ultimo report reale sincronizzato su `sidee-reports`:

`sidee-20260926-182425-cbe7`

Build:

```text
clientBuildId = app-a009a09c47aa
serverBuildId = app-a009a09c47aa
buildMatch = true
accessMode = VIDAAHUB_BROWSER_CONTEXT
```

Il probe `pkgmgrPackageCorrelation` è riuscito realmente:

```text
status = READ_OK
AppInfo count = 3
pkgmgr packages = 18
matches = 0
```

Le tre entry reali di `websdk/Appinfo.json` restano:

1. Smartone IPTV — ID 1470 — URL web remota — StoreType `store`;
2. Stremio Lite — ID 2568 — URL web remota — StoreType `hisense`;
3. Duplecast — ID 1876 — URL web remota — StoreType `store`.

I package `pkgmgr` sono invece componenti `tv.vidaa.*` di sistema/runtime, inclusi browser, phoenix, operationui, jsservice, librerie e risorse.

Non c'è alcuna correlazione reale tra le tre web app launcher e i 18 package.

Conclusione confermata:

```text
websdk/Appinfo.json = registry delle web app launcher/store
pkgmgr              = package manager di componenti/packages VIDAA
```

Quindi non conviene usare `pkgmgr install` con package name inventati come tentativo di installare Nuvio.

---

# Cosa considero ormai escluso o fortemente ridimensionato

Sulla Hisense:

```text
50E70LEVS_0003
VIDAA U09.60
V0000.09.60A.Q0707
MTK9603
Odin/Chromium ~111
```

abbiamo già verificato abbastanza da non ripetere:

### 1. Hisense_installApp / Hisense_installApp_V2

Entrambi arrivano a:

```text
installApplication
ret:false
code:503
client request permission check error, please check appconfig
```

Callback esterno `0` non prova l'installazione.

### 2. Direct AppInfo fileWrite

Il no-op protetto su:

`websdk/Appinfo.json`

restituisce lo stesso:

```text
ret:false
code:503
client request permission check error, please check appconfig
```

con readback identico.

Quindi il gate non riguarda solo `installApplication`.

### 3. Origin / DNS

Provato sia:

```text
https://vidaahub.com
```

sia:

```text
http://192.168.1.5:8080
```

`fileRead` passa, `fileWrite` resta 503.

DNS/origin non sono la variabile sufficiente.

### 4. Identifier JavaScript

Provati contro il vero write gate:

```text
1470
1876
2568
```

come override temporaneo di `vowOS.service.getIdentifier()`.

Risposta identica alla baseline:

```text
IDENTIFIER_STRING_NOT_SUFFICIENT
```

### 5. Vero store-app context

Smartone e Duplecast lanciati realmente dal VIDAA launcher hanno identity native vere.

Esempio Duplecast:

```text
appId = 1876
navigator.appIdentifier = {
  appid: "1876",
  md5: "...",
  permissions: ""
}
service identifier = non vuoto
Hisense_SupportAppConfig() = true
```

ma il no-op `fileWrite` continua a essere respinto con 503.

Quindi:

```text
REAL_INSTALLED_APP_IDENTITY != WRITE_PERMISSION
```

### 6. HSPDK legacy

Nel normale browser e in Smartone non abbiamo:

```text
HiBrowser
Hisense.File
Hisense.loadLibrary
File.read + File.write
```

Il runtime storico `modeljs.sendam` e i marker `hi_browser/lau_browser/tv_store` non sono esposti nel browser Q0707.

Non conviene tornare ora a lanciare nomi legacy alla cieca.

### 7. pkgmgr come percorso per le normali web app Store

`vowOS.store.getInstalledPkgs()` è reale e autorizzato, ma i 18 package risultano separati dalle tre web app AppInfo.

`tv.vidaa.app.tvbrowser` è un package web di sistema, non la prova che Smartone/Duplecast/Stremio vengano installati tramite pkgmgr.

Non è emerso alcun downloader/stager browser-side collegato alle normali app web Store.

---

# Nuovo dato importante trovato in questa analisi

La fonte pubblica più interessante emersa ora è:

`PhasedGapple/FuVIDAA-API`

File:

`Project FuckVIDAA/main.cpp`

Commit verificato:

`e2010891e5061698d537e77164f3489d4c087011`

Il codice crea realmente un server HTTPS locale per:

```text
category-ui.vidaahub.com
```

e usa il vero backend upstream:

```text
https://category-ui.vidaahub.com
```

Le richieste non gestite vengono inoltrate all'upstream.

Soprattutto, il PoC sovrascrive concretamente:

```text
/api/v1.0.0/categoryApi/categoryFirstResult
```

restituendo una risposta di catalogo VIDAA con una tile app completa.

La tile contiene realmente campi come:

```text
id
original
productCode = "600"
typeCode = "600002"
showInfo
appInfo.url
appInfo.openMode
appInfo.unifiedAppName
appInfo.configUrl
appInfo.configUrlDownload
appInfo.hasDetailPage
appInfo.packaged
appInfo.appBundle
appContentId
appHasDetailPage
signatureServer
```

Nel PoC l'app inserita è:

```text
id = 2446
url = https://smarttv.unicoplay.com/hisense/
openMode = "99"
unifiedAppName = "2446"
packaged = 0
```

## Perché questo cambia la priorità

Questo non dimostra ancora che si possa installare Nuvio sulla nostra Q0707.

Non dimostra nemmeno che modificare `categoryFirstResult` sia sufficiente per completare un'installazione.

Però dimostra una cosa che prima non avevamo:

> esiste una superficie separata del vero VIDAA Store, `category-ui.vidaahub.com`, che fornisce al frontend Store metadata completi delle web app prima che queste finiscano nel registry locale AppInfo.

Quindi la domanda utile non è più:

```text
Come convinciamo il browser vidaahub.com a scrivere AppInfo?
```

ma:

```text
Qual è il flusso reale Store
category-ui -> metadata/detail -> azione install/open -> AppInfo registration,
e quale componente privilegiato esegue l'ultima fase?
```

Questo è coerente con tutti i risultati già ottenuti:

- il browser normale può leggere ma non scrivere;
- una normale web app installata ha identity nativa ma non write ACL;
- AppInfo contiene metadata Store molto più ricchi di quelli costruiti dal wrapper `Hisense_installApp`;
- `pkgmgr` è un livello separato;
- deve quindi esistere da qualche parte un flusso Store/system che materializza quelle entry.

---

# Ipotesi aggiornata sulle soluzioni possibili

## Pista principale — official Store backend / Store UI context

È ora la pista con il miglior rapporto tra evidenza concreta e testabilità.

Possibile architettura:

```text
category-ui.vidaahub.com
        ↓
catalog/detail metadata
        ↓
VIDAA Store / Operation UI
        ↓
azione nativa privilegiata
        ↓
AppInfo registration
```

La parte da verificare è tutto ciò che sta dopo il catalogo.

Non dobbiamo assumere che l'endpoint di catalogo installi direttamente.

Dobbiamo osservare il vero Store mentre:
- apre la home/categoria;
- apre una detail page;
- visualizza una app già installata;
- eventualmente mostra Open/Install.

Solo dopo possiamo vedere quali endpoint/action aggiuntivi vengono usati.

## Seconda pista — operationui / bridge Store di sistema

Nel `pkgmgr` reale esiste:

```text
tv.vidaa.app.operationui
type = system
```

Non abbiamo ancora provato che sia il processo che gestisce il VIDAA Store.

Quindi NON va trattato come fatto.

Però è un candidato concreto da correlare in futuro con il traffico Store, perché è un package di sistema realmente installato sulla TV.

La ricerca deve partire dal traffico reale, non dal nome.

## Terza pista — AppConfig ACL nativa

I test hanno già mostrato che il controllo è sotto il wrapper JavaScript.

È molto plausibile che il backend locale associ permessi a un client/AppConfig non riproducibile semplicemente con:
- origin;
- hostname;
- app ID;
- service identifier;
- normale store-app launch context.

Questa resta la spiegazione tecnica più coerente del 503.

Ma cercare di “indovinare” l'ACL o i suoi token non è una strategia efficace.

Meglio arrivare al processo ufficiale che possiede già quel privilegio.

## HSPDK / legacy

Resta una pista storica interessante, ma oggi ha evidenza inferiore rispetto al vero Store moderno.

Non la eliminerei dal progetto, ma non la userei come prossima fase.

---

# Cosa fare adesso

Il prossimo test non deve installare nulla.

Deve essere un:

```text
VIDAA Store Catalog / Transport Trace
```

completamente osservazionale.

## Fase A — intercettare solo il vero traffico Store

Aggiungere a Sidee supporto mirato per:

```text
category-ui.vidaahub.com
```

ma NON servire la normale UI Sidee su quell'host.

Sidee deve comportarsi come proxy trasparente verso:

```text
https://category-ui.vidaahub.com
```

registrando solo informazioni diagnostiche ridotte.

### Dati da registrare

Per ogni request Store:

- timestamp;
- host;
- metodo;
- path;
- nomi delle query parameter, non valori sensibili;
- status upstream;
- content-type;
- lunghezza;
- se JSON:
  - top-level keys;
  - endpoint/category semantic fields utili;
  - app ID/unifiedAppName solo se presenti nei normali metadata catalogo;
- eventuale endpoint relation tra category/detail/action.

### Dati da NON salvare

Redigere/non persistire:

- Cookie;
- Authorization;
- access token;
- refresh token;
- session ID;
- signature material;
- device identifier sensibili;
- header che sembrano token/key/auth/signature.

Se servono per far funzionare il proxy, possono essere inoltrati all'upstream senza essere scritti nel report.

### Nessuna modifica della risposta nella prima fase

La prima versione deve essere:

```text
PASS-THROUGH ONLY
```

Niente tile custom.

Niente Nuvio.

Niente modifica JSON.

Niente install.

Niente AppInfo write.

Scopo:

> verificare se la nostra TV Q0707 usa davvero `category-ui.vidaahub.com`, quali endpoint chiama oggi e cosa succede quando si apre una app nello Store.

---

# Nota TLS importante

Il PoC FuVIDAA usa un certificato/key dedicato a:

```text
category-ui.vidaahub.com
```

Sidee al momento genera il certificato per:
- vidaahub.com;
- www.vidaahub.com;
- Smartone;
- Duplecast.

Per il nuovo probe bisogna aggiungere il SAN:

```text
DNS:category-ui.vidaahub.com
```

e fare in modo che un certificato già esistente senza questo SAN NON venga riutilizzato silenziosamente.

Meglio:
- cambiare il nome/versione del cert Sidee; oppure
- verificare i SAN e rigenerarlo quando manca il nuovo host.

Non assumere che il VIDAA Store accetti il certificato self-signed.

Il test deve distinguere:

```text
DNS hit
TLS SNI hit
HTTP request arrivata
```

così anche un eventuale rifiuto TLS produce un risultato utile.

Interpretazione:

### Caso A

```text
nessun DNS hit per category-ui
```

La TV/Store corrente non usa quell'host nel flusso testato.

### Caso B

```text
DNS hit
TLS SNI hit
nessuna HTTP request
```

L'host è corretto ma il TLS/cert blocca l'intercettazione.

Non modificare payload; risolvere prima solo il trasporto.

### Caso C

```text
HTTP passa
categoryFirstResult compare
```

Il PoC è compatibile almeno a livello di backend/catalogo con la nostra generazione.

Seguire i successivi endpoint reali.

### Caso D

```text
HTTP passa ma usa endpoint diversi
```

Ignorare il vecchio endpoint e seguire esclusivamente quelli osservati sulla Q0707.

---

# Fase B — solo dopo un trace reale riuscito

Se il proxy pass-through dimostra che il VIDAA Store usa davvero quel backend, il test successivo non deve ancora essere Nuvio.

Prima fare un catalog injection innocuo e reversibile usando **una app già installata**, per esempio Smartone o Duplecast.

Obiettivo:

```text
provare che il frontend Store consuma la nostra risposta modificata
```

senza richiedere un nuovo write locale.

Esempio concettuale:
- prendere una tile reale già restituita;
- oppure usare metadata reali di Smartone/Duplecast;
- cambiare solo un elemento visuale innocuo/titolo di test;
- non cambiare ID/URL in modo da creare una nuova app;
- verificare se la UI Store riflette la risposta.

Solo dopo aver provato il controllo sul catalogo, osservare cosa succede quando si entra nella detail page di una app reale.

Il primo vero test d'installazione dovrebbe arrivare soltanto quando conosciamo:
- endpoint detail;
- eventuale endpoint action;
- payload;
- risposta;
- componente che effettua la registrazione.

---

# Cosa NON fare nella prossima chat

Non tornare a:

- `Hisense_installApp`;
- `Hisense_installApp_V2`;
- fileWrite no-op;
- raw IP;
- identity override 1470/1876/2568;
- Smartone/Duplecast no-op write;
- HSPDK browser vs Smartone;
- modeljs/hi_browser inventati;
- `pkgmgr install` con package name inventato;
- variazioni di `APPS:pkgs` path;
- callback `0`;
- brute force di OMI action/type;
- brute force di HiUtils API.

Questi dati sono già sufficientemente documentati.

---

# Fonti nuove da conservare

## FuVIDAA-API

Repository:

https://github.com/PhasedGapple/FuVIDAA-API

File:

`Project FuckVIDAA/main.cpp`

Commit osservato:

`e2010891e5061698d537e77164f3489d4c087011`

Fatti verificati nel source:
- server SSL locale con cert/key `category-ui.vidaahub.com`;
- upstream `https://category-ui.vidaahub.com`;
- proxy delle GET non gestite;
- override di `/api/v1.0.0/categoryApi/categoryFirstResult`;
- risposta compatibile con tile/appInfo VIDAA.

Affidabilità:

```text
CODICE PUBBLICO / PoC DI TERZI
```

Non è documentazione Hisense e non prova il successo dell'installazione sulla Q0707.

## HiZ-Store issue #1

https://github.com/PhasedGapple/HiZ-Store/issues/1

Resta utile come contesto storico:
- fileWrite ha funzionato su alcune TV/firmware;
- è stato poi riportato come patchato/non affidabile su nuove VIDAA 9;
- simonbuehler ha dichiarato di aver ottenuto developer mode / controllo del servizio con inspection, ma il thread pubblico verificato non fornisce un percorso minimo moderno completo applicabile alla nostra Q0707 oltre al fileWrite già testato.

Quindi non usare quelle dichiarazioni come prova di un bypass disponibile.

---

# Prossima chat — prompt pronto

Sto continuando il lavoro su `Empi9245/Sidee`, branch `main`.

Lavora direttamente sulla repo e committa direttamente su `main`.

**NON usare devkit.**

Prima di modificare:

- leggi completamente `AI_CONTEXT.md`;
- leggi `README.md`;
- leggi `LATEST_RESPONSE_AND_NEXT_CHAT.md`;
- controlla HEAD reale di `main`;
- controlla `reports/latest.json` sul branch `sidee-reports`;
- controlla `sidee.py`, `config.json`, `web/app.js`, `web/index.html`, `web/hspdk-context.js`.

Non rifare i test già chiusi:
- install legacy/V2 -> AppConfig 503;
- direct AppInfo fileWrite -> AppConfig 503;
- raw-IP vs vidaahub;
- identifier override 1470/1876/2568;
- Smartone/Duplecast launcher context no-op write;
- HSPDK browser/Smartone;
- pkgmgr come registry delle normali web app;
- variazioni path `APPS:pkgs`.

## Nuovo dato fondamentale

È stato verificato il source pubblico:

`PhasedGapple/FuVIDAA-API/Project FuckVIDAA/main.cpp`

commit:

`e2010891e5061698d537e77164f3489d4c087011`

Il PoC crea un server HTTPS per:

`category-ui.vidaahub.com`

inoltra richieste al vero:

`https://category-ui.vidaahub.com`

e sovrascrive:

`/api/v1.0.0/categoryApi/categoryFirstResult`

con una risposta catalogo VIDAA che contiene una tile app completa con:

`id / productCode / typeCode / showInfo / appInfo.url / openMode / unifiedAppName / configUrl / packaged / appBundle / signatureServer`.

Questo non prova l'installazione su Q0707, ma dimostra che il vero catalogo Store è una superficie separata che precede AppInfo.

## Obiettivo di questa fase

Implementa un **VIDAA Store Catalog / Transport Trace** pass-through e read-only dal punto di vista della TV.

Prima fase: nessuna modifica delle risposte Store.

### Requisiti

1. Aggiungi `category-ui.vidaahub.com` ai domini Sidee necessari per il probe.
2. Aggiorna il certificato/SAN includendo `category-ui.vidaahub.com`.
3. Assicurati che un vecchio cert privo del SAN non venga riutilizzato.
4. Per richieste HTTPS con Host `category-ui.vidaahub.com`:
   - non servire la UI Sidee;
   - proxy verso il vero `https://category-ui.vidaahub.com`;
   - preserva il più possibile metodo/path/query e request body necessari;
   - inoltra i dati necessari senza salvarne i segreti.
5. Registra in un trace bounded:
   - DNS hit;
   - TLS SNI hit;
   - HTTP method;
   - path;
   - soli nomi delle query parameter;
   - status upstream;
   - content-type;
   - response length;
   - per JSON: top-level keys e metadata app/catalog non sensibili.
6. REDACT completamente nei report:
   - Cookie;
   - Authorization;
   - access/refresh token;
   - token/session/key/signature/certificate/nonce/password/credential-like values.
7. Non modificare il body upstream.
8. Non iniettare tile custom.
9. Non eseguire install.
10. Non eseguire fileWrite.
11. Non invocare HiUtils/OMI action inventate.
12. Salva il risultato nel report di sessione in una sezione tipo:
   `storeCatalogTrace`.
13. Esponi un piccolo status locale che faccia capire:
   - DNS_ONLY;
   - TLS_SNI_ONLY;
   - HTTP_PROXY_ACTIVE;
   - REQUESTS_CAPTURED;
   - PROXY_ERROR.
14. Mantieni la normale UI `vidaahub.com` funzionante.
15. Aggiorna `AI_CONTEXT.md` con la fonte FuVIDAA e con l'implementazione fatta.
16. Fai test locali senza TV:
   - parsing Python;
   - proxy request/response mock;
   - redaction di token/cookie/auth;
   - SAN/build ID;
   - nessuna modifica del body upstream;
   - normale Sidee host ancora servito;
   - category-ui trattato separatamente.
17. Commit direttamente su `main`.

## Test reale da preparare per me

Dopo pull + restart:

1. TV DNS -> PC Sidee;
2. non aprire Smartone/Duplecast;
3. aprire il **VIDAA Store ufficiale** dal launcher;
4. navigare una categoria;
5. aprire la scheda di una app reale, preferibilmente una già installata;
6. non premere Install se non necessario;
7. attendere il sync del report;
8. analizzare `storeCatalogTrace`.

La prima domanda da risolvere è:

```text
La Q0707 usa davvero category-ui.vidaahub.com e quali endpoint chiama
quando il VIDAA Store apre catalogo e dettaglio app?
```

Se il trace arriva, il prossimo passo dovrà seguire esclusivamente gli endpoint reali osservati.

Se arriva solo DNS/SNI ma non HTTP, fermarsi sul problema TLS/trasporto senza inventare endpoint.

Se non arriva nemmeno DNS, ridimensionare questa pista e cercare il backend realmente usato dalla Q0707.
