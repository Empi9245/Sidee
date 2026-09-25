# Sidee — AI Context / Research Notes

> Read this file before doing new VIDAA research or changing the installer.
> Goal: avoid repeating already completed research, tests, and conclusions.

Last updated: 2026-09-25

## Project

Repository: `Empi9245/Sidee`
Branch: `main`

Sidee is a standalone local diagnostic/installer lab for Hisense VIDAA TVs.
It is intentionally separate from Nuvio TV.

Primary target app during current testing:
- Repo: `Empi9245/nuviotvsmart`
- App ID: `nuviodebug`
- App name: `Nuvio TV`
- Test URL: `http://192.168.1.5:4173/?wrapper=vidaa`
- Icon: `http://192.168.1.5:4173/assets/images/icon.png`

Sidee provides:
- DNS spoof for `vidaahub.com`
- HTTPS host on port 443
- dashboard/fallback on port 8080
- VIDAA API discovery
- legacy and V2 install tests
- OMI launcher refresh
- installed-app verification
- read-only `websdk/Appinfo.json` inspection
- JSON reports saved on the PC

## Tested TV

Real hardware used for the current research:

- Brand: Hisense
- Model: `50E70LEVS_0003`
- Firmware: `V0000.09.60A.Q0707`
- OS: `VIDAA U09.60`
- VIDAA API version: `3.0.1`
- Chipset: `MTK9603`
- Runtime: Chromium 111
- Browser reported by VIDAA: `odin`
- Region: `EU_A`
- Country: `ITA`
- Panel: `3840*2160`
- TV LAN IP during tests: `192.168.1.10`

The Sidee page was successfully executed from:
- `https://vidaahub.com/`
- origin: `https://vidaahub.com`

Therefore the DNS/HTTPS setup is confirmed to reach the privileged VIDAA browser context on this TV.

## Important APIs confirmed on this firmware

The firmware exposes, among many others:

- `Hisense_installApp`
- `Hisense_installApp_V2`
- `Hisense_uninstallApp`
- `Hisense_getInstalledApps`
- `Hisense_FileRead`
- `Hisense_FileWrite`
- `Hisense_SupportAppConfig`
- `HiUtils_createRequest`
- `omi_platform`
- `opera_omi`

`HiUtils_createRequest` is implemented by the firmware as a wrapper around:

`vowOS.service.syncExecute('hiutils', { api: type, args: msg })`

Do not assume an API is usable just because the JavaScript function exists.

## Key discovery: install callback 0 is NOT proof of installation

Earlier tools, including simple installers based on `Hisense_installApp`, may report success when the callback returns `0`.

On this firmware this is misleading.

Sidee now verifies installation using:
1. `Hisense_getInstalledApps`
2. read-only `websdk/Appinfo.json`
3. before/after snapshots
4. internal HiUtils tracing where possible

A callback of `0` must be treated only as "request accepted by the JavaScript wrapper", not as "app installed".

## Real install test results

Both install methods have been tested against the real Nuvio target.

### Legacy: `Hisense_installApp`

Observed behavior:
- JavaScript callback: `0`
- wrapper return value: `false`
- launcher refresh through OMI: attempted
- Nuvio absent from `Hisense_getInstalledApps`
- Nuvio absent from `websdk/Appinfo.json`
- final verification: `false`

The internal call reaches HiUtils and fails at:

`installApplication`

with:

- `ret: false`
- `code: 503`
- message: `client request permission check error, please check appconfig`

### V2: `Hisense_installApp_V2`

Observed behavior is effectively the same:
- callback can still report `0`
- function return value is `false`
- internal `installApplication` call fails
- app is not added to installed apps
- app is not added to `Appinfo.json`

Real internal error:

`client request permission check error, please check appconfig`

Code:

`503`

## Current main conclusion

The current blocker is NOT:

- Nuvio URL
- Nuvio application code
- wrong icon
- wrong app ID alone
- missing OMI refresh
- failure to reach `vidaahub.com`
- absence of the install APIs
- difference between legacy and V2 install APIs
- total lack of HiUtils access

The blocker is the firmware's internal client permission / appconfig check for the privileged `installApplication` operation.

The TV permits useful read access, including reading `websdk/Appinfo.json`, but rejects the install write path.

## Relevant external research already checked

### Stremio Hisense installer

Repository:
`Stremio/stremio-hisense-install`

Useful findings already incorporated:
- uses `vidaahub.com`
- uses `Hisense_installApp`
- sends an OMI `AllAppsUpdate` message after install
- historically assumes callback `0` means success

Do not copy that success assumption.

### vidaa-edge

Repository:
`weinzii/vidaa-edge`

Useful findings already incorporated:
- broad VIDAA API discovery
- legacy install API
- V2/install-related research
- Appinfo read/write research
- function-source discovery

Relevant issue:
`weinzii/vidaa-edge#30`

That issue reports the same firmware-family behavior:
`client request permission check error, please check appconfig`

Reported affected VIDAA 9.60 firmwares include examples such as:
- `V0000.09.60F.Q0528`
- `V0000.09.60C.Q0516`
- `V0000.09.60A.Q0602`

Our tested firmware:
- `V0000.09.60A.Q0707`

This strongly suggests the permission restriction is firmware-family behavior, not a Nuvio-specific failure.

## Important implementation notes

Current Sidee main includes:
- automatic correction when icon URL accidentally equals app URL
- separate Legacy and V2 install buttons
- HiUtils tracing around install calls
- Appinfo snapshots before/after
- verification after callback and launcher refresh

Current known good Nuvio icon path:
`/assets/images/icon.png`

Do not use the Nuvio page URL itself as the icon.

## Things NOT to repeat blindly

Do not spend time re-testing these assumptions unless new evidence appears:

1. "Try callback 0 again" — already disproved as a success signal.
2. "Maybe V2 works when legacy does not" — both reach the same permission failure.
3. "Maybe OMI refresh is missing" — refresh already runs; app was never registered.
4. "Maybe the icon is invalid" — corrected and retested.
5. "Maybe Nuvio URL is unreachable" — Nuvio is reachable on the LAN and serves the VIDAA build.
6. "Maybe Sidee is not really running under vidaahub.com" — confirmed it is.
7. "Maybe Appinfo cannot be read" — on this specific TV it can be read.
8. "Maybe direct fileWrite should be tried immediately" — do not jump to this.

## Safety / scope

Do NOT automatically:
- force-write `websdk/Appinfo.json`
- corrupt or replace launcher databases
- call `Hisense_ResetDevice`
- use service-menu tricks
- downgrade firmware
- modify bootloader/system partitions
- bypass signing through destructive system changes

Presence detection, source inspection, read-only file reads and non-destructive probes are acceptable.

Direct Appinfo writes remain intentionally disabled in Sidee unless a later device-specific method is understood and explicitly opted into with safeguards.

## Best next research direction

The next useful work is NOT another blind install attempt.

Investigate the appconfig / permission layer safely.

Recommended next probe:
- enumerate globals/functions containing:
  - `appconfig`
  - `permission`
  - `access`
  - `client`
  - `config`
  - `installApplication`
- capture sources where available
- inspect `Hisense_SupportAppConfig()`
- inspect relevant read-only HiUtils requests
- inspect the browser/client identity used by `vowOS`
- compare allowed read operations vs blocked install operations
- look for documented appconfig metadata already loaded in the page/runtime
- avoid speculative writes

The goal is to answer:

"What exact appconfig/client permission does VIDAA 9.60 require for `installApplication`, and is there a supported/exposed way for a vidaahub.com client to obtain it?"

## Reports already produced during this investigation

Local report filenames seen during testing:

- `vidaa-20260925-174651-856214.json` — initial read-only API scan
- `vidaa-20260925-180251-277424.json`
- `vidaa-20260925-180304-691675.json`
- `vidaa-20260925-180324-294314.json`
- `vidaa-20260925-181319-290491.json` — V2 install test
- `vidaa-20260925-181332-307152.json` — Legacy install test
- `vidaa-20260925-181401-996903.json`
- `vidaa-20260925-181411-919592.json`

Reports may remain local because `reports/*.json` can be ignored by Git. The conclusions above summarize the important findings so another AI does not need those files just to reconstruct the investigation.

## Instructions for future AI agents

Before making changes:
1. Read this file.
2. Read the current `README.md`.
3. Check current `main` HEAD.
4. Inspect current `web/app.js` before modifying install logic.
5. Preserve the distinction between JavaScript callback success and verified installation.
6. Prefer evidence from the exact TV/firmware over assumptions from older VIDAA versions.
7. Do not reintroduce an invented public Nuvio URL.
8. Keep Sidee standalone from Nuvio.

When a new report is provided, compare it against the known baseline above rather than restarting the investigation.


---

## UPDATE RICERCA — 2026-09-25, dopo analisi AppConfig/Permission

Questa sezione documenta tutto ciò che è stato verificato nella chat successiva all'ultimo aggiornamento del file.

### Stato Git reale prima di questa ricerca

Al momento della verifica, `main` era ancora esattamente su:

`f2beaae5dbcb30fd85c0a0220f58b292f5ad4d50`

commit:

`docs: add VIDAA AI research context`

Non risultavano commit successivi.

IMPORTANTE: durante questa chat sono state preparate idee/modifiche per il nuovo probe/UI/report, ma NON erano ancora state applicate a `main` prima di questo aggiornamento del contesto. Quindi la prossima AI deve prima controllare lo stato reale del branch e non assumere che il refactor diagnostico sia già presente.

### Ricerca pubblica ricontrollata

È stata ricontrollata la issue:

`weinzii/vidaa-edge#30`

Titolo:

`client request permission check error on firmware V0000.09.60F.Q0528 (May 2026)`

Stato verificato il 2026-09-25:

- issue ancora aperta;
- ultimo aggiornamento pubblico trovato: 2026-09-09;
- continua a non esserci una soluzione pubblica/documentata al controllo AppConfig/client permission.

Commenti rilevanti confermati:

1. 2026-08-23, maintainer `weinzii`:
   sostiene che su firmware >= v9 `vidaahub.com` possa funzionare senza DNS rewrite.

   Per Sidee questo non cambia la priorità:
   sulla TV reale Sidee gira già correttamente sotto `https://vidaahub.com` con origin corretto, quindi il DNS non è il blocker attuale.

2. 2026-08-26, firmware:

   `V0000.09.60C.Q0516`

   stesso errore con e senza DNS rewrite.

3. 2026-09-09, firmware:

   `V0000.09.60A.Q0602`

   vengono caricate correttamente circa 104 funzioni, ma l'installazione fallisce ancora con:

   `client request permission check error, please check appconfig`

   In quel caso viene anche segnalata assenza di `Hisense_FileRead`, mentre sulla TV usata per Sidee il read-only di Appinfo via HiUtils è già stato verificato come funzionante.

Conclusione aggiornata:

il comportamento continua a essere coerente con una restrizione della famiglia firmware VIDAA 9.60, non con un problema specifico di Nuvio o del DNS.

### Ricerca su `Hisense_SupportAppConfig`

Nel repository `weinzii/vidaa-edge`, `Hisense_SupportAppConfig` compare nell'inventario delle funzioni Hisense in:

`src/global.d.ts`

ma non è stato trovato un uso concreto pubblico che spieghi:

- parametri;
- formato del risultato;
- relazione con `installApplication`;
- relazione con il controllo client/appconfig;
- eventuale modo supportato per ottenere privilegi aggiuntivi.

Quindi rimane una funzione da analizzare direttamente sul runtime della TV.

### Altri nomi API trovati che potrebbero essere collegati a sicurezza/client identity

Nell'inventario pubblico delle funzioni VIDAA sono stati confermati anche nomi potenzialmente interessanti:

- `Hisense_HiSdkSignCreate`
- `Hisense_HiSdkSignCreateSoundbar`
- `Hisense_HiSdkJsonVerifyHeap`
- `Hisense_CheckAccessCode`
- `Hisense_CheckCodeValid`
- `Hisense_GetRoleID`
- `Hisense_SetRoleID`
- `Hisense_GetCustomerID`
- `Hisense_SetCustomerID`
- `Hisense_Encrypt`
- `Hisense_Decrypt`
- `Hisense_RSADecrypt`

Questi nomi NON provano che siano collegati al blocco AppConfig.

Policy per Sidee:

- possono essere enumerati;
- possono essere ispezionati via descriptor/source quando possibile;
- NON devono essere chiamati automaticamente se possono cambiare stato o richiedere credenziali/firme;
- in particolare `SetRoleID`, `SetCustomerID`, funzioni di firma/access code, reset e write restano fuori dal probe automatico.

### `HiUtils_createRequest`

Rimane confermato sul firmware reale che:

`HiUtils_createRequest(type, msg)`

wrappa essenzialmente:

`vowOS.service.syncExecute('hiutils', { api: type, args: msg })`

Nuova conclusione operativa:

non è stato trovato un elenco pubblico affidabile di nomi HiUtils read-only specifici per AppConfig/permission.

Quindi Sidee NON deve:

- inventare nomi di API HiUtils;
- brute-forzare stringhe;
- chiamare automaticamente API sconosciute.

Può invece:

- ispezionare il source di `HiUtils_createRequest`;
- ispezionare `vowOS` e proprietà correlate senza invocare getter sconosciuti;
- estrarre nomi/stringhe concrete trovate nel source/runtime;
- testare solo richieste read-only già note o scoperte con alta confidenza;
- continuare a usare il `fileRead` già verificato per `websdk/Appinfo.json`.

### Direzione del nuovo Permission/AppConfig Probe

Il matcher di `enumerateInterestingGlobals()` deve essere esteso almeno a:

- `appconfig`
- `appConfig`
- `permission`
- `permissions`
- `access`
- `client`
- `whitelist`
- `domain`
- `origin`
- `security`
- `installApplication`
- `config`
- `capability`
- `privilege`
- `auth`
- `certificate`
- `signature`
- `sign`
- `vowOS`
- `hiutils`
- `Hisense_SupportAppConfig`

Il probe non deve limitarsi ai nomi globali.

Deve poter ispezionare in modo sicuro proprietà di oggetti interessanti, salvando quando possibile:

- path completo;
- nome proprietà;
- tipo;
- valore primitivo se già presente come data property;
- descriptor;
- source delle funzioni;
- source dei getter/setter SENZA invocarli;
- errori di accesso;
- info sul prototype;
- proprietà enumerate;
- riferimenti interessanti trovati nel source.

Devono esserci limiti rigidi a:

- profondità;
- numero proprietà;
- numero totale entry;
- lunghezza stringhe;
- lunghezza source;
- circular references.

### Chiamate che il nuovo probe può eseguire

Nuova proposta sicura:

1. i getter VIDAA già considerati read-only e già usati nello scan;
2. `Hisense_SupportAppConfig()` senza parametri, se presente;
3. `HiUtils_createRequest('fileRead', {path:'websdk/Appinfo.json', mode:6})` nella fase di verification, perché già verificato sulla TV reale.

Il Permission/AppConfig probe NON deve eseguire automaticamente:

- getter/accessor sconosciuti;
- nomi HiUtils inventati;
- `Hisense_HiSdkSignCreate*`;
- `Hisense_CheckAccessCode`;
- `Hisense_CheckCodeValid`;
- `Hisense_FileWrite`;
- `fileWrite`;
- `Set*`;
- reset;
- install/uninstall.

Install e uninstall restano azioni esplicite separate dal probe.

### Nuova ipotesi concreta sul controllo AppConfig

La migliore ipotesi attuale, da trattare ancora come ipotesi e non come fatto provato, è:

1. il browser/origin espone correttamente le funzioni JavaScript Hisense;
2. il wrapper nativo riceve la richiesta;
3. `installApplication` arriva al servizio interno HiUtils;
4. prima dell'operazione di scrittura/registrazione viene eseguito un controllo sul client;
5. il client corrente non possiede una permission/AppConfig richiesta;
6. il firmware risponde quindi con code 503 e:
   `client request permission check error, please check appconfig`.

La parte ancora sconosciuta è:

- quale metadata identifica il client;
- dove si trova l'AppConfig effettivo;
- se il browser `odin` carica un permission set specifico;
- se origin/domain/signature/role/customer id partecipano al controllo;
- se esiste una API read-only che esponga tali informazioni;
- se `Hisense_SupportAppConfig` restituisce dati utili.

### Architettura report proposta

La prossima implementazione dovrebbe sostituire i molti report quasi duplicati con:

`una sessione diagnostica = un report principale`

Formato session ID suggerito:

`sidee-YYYYMMDD-HHMMSS-xxxx`

Nome file suggerito:

`sidee-session-YYYYMMDD-HHMMSS-xxxx.json`

Backend proposto:

`POST /api/reports/session`

con:

- validazione stretta di `sessionId`;
- filename derivato server-side;
- nessun path arbitrario accettato;
- scrittura atomica;
- update/sovrascrittura dello stesso JSON;
- compatibilità mantenuta con `/api/reports/latest`;
- lista report ancora disponibile.

Struttura report proposta:

- `sessionId`
- `startedAt`
- `updatedAt`
- `summary`
- `environment`
- `permissionProbe`
- `target`
- `installDiagnostic`
- `verification`
- `raw.snapshots`

### Compact Installed Apps / Appinfo

Per evitare report enormi:

`Hisense_getInstalledApps` e `websdk/Appinfo.json` dovrebbero avere una vista compatta con:

- count;
- id;
- name/title;
- URL/start command;
- store type;
- matchedTarget.

I raw completi dovrebbero essere conservati una sola volta per snapshot significativo, per esempio:

- `installedAppsBefore`
- `installedAppsAfter`
- `appInfoBefore`
- `appInfoAfter`

e non duplicati dentro ogni step.

### Regola false positive da mantenere assolutamente

Callback JavaScript `0` NON equivale mai a successo.

Se il trace interno mostra:

- `ret:false`
- `code:503`
- `client request permission check error, please check appconfig`

la classificazione deve essere:

`REJECTED`

L'unico successo finale valido deve essere:

`VERIFIED INSTALLED`

quando la verifica trova realmente l'app.

### UI proposta

Workflow TV lineare da implementare:

1. Device / Environment Scan
2. Permission & AppConfig Probe
3. Target App Configuration
4. Install Diagnostic
5. Verification
6. Export Report

Summary sempre visibile con almeno:

- Environment
- Origin
- Install API
- AppConfig probe
- Install request
- Internal reason
- Permission code
- Verification

Legacy/V2 devono diventare controlli diagnostici secondari/advanced.

L'azione principale dovrebbe essere:

`Run install diagnostic`

che può fare:

Legacy -> verification -> V2 -> verification

senza presentare V2 come "soluzione alternativa".

### Stato implementazione alla fine di questa ricerca

IMPORTANTE PER LA PROSSIMA CHAT:

la ricerca sopra è stata completata, ma il refactor del codice NON era ancora stato pubblicato su `main` al momento di questa nota.

Quindi prima di continuare:

1. leggere questo file;
2. controllare l'HEAD reale di `main`;
3. controllare `web/app.js`, `web/index.html`, `web/style.css`, `sidee.py`;
4. verificare quali parti del nuovo probe/report/UI risultano effettivamente presenti;
5. implementare solo ciò che manca;
6. non rifare la ricerca già documentata qui.

### Prossimo test reale consigliato sulla Hisense

Quando il nuovo probe sarà effettivamente implementato:

1. avvia Sidee sul PC;
2. imposta il DNS della TV sul PC;
3. apri `https://vidaahub.com`;
4. esegui Device / Environment Scan;
5. esegui Permission & AppConfig Probe;
6. controlla soprattutto `Hisense_SupportAppConfig`, `vowOS`, `HiUtils_createRequest` e riferimenti permission/client/security;
7. configura Nuvio se necessario;
8. esegui Run Install Diagnostic;
9. lascia completare Legacy + V2 + verification;
10. esporta il report;
11. invia il singolo `sidee-session-....json` della sessione.

Non serve committare i report generati.


---

## Protocollo ricerca esterna / GitHub — evitare spreco di token

Questa regola vale per tutte le prossime chat che lavorano su Sidee.

Quando si fa ricerca su Internet o GitHub, NON lasciare che la ricerca viva solo nella chat.

Ogni informazione esterna che modifica una conclusione, introduce una nuova API, conferma/smentisce un'ipotesi o suggerisce un test concreto deve essere sintetizzata in `AI_CONTEXT.md` nello stesso lavoro, con:

- data della verifica;
- fonte precisa (repo/file/issue/comment/documentazione/pagina);
- fatto osservato;
- livello di affidabilità: confermato / riportato da terzi / ipotesi;
- conseguenza pratica per Sidee;
- cosa NON serve ricercare di nuovo;
- eventuale prossimo test sulla TV.

### Regola di efficienza per GitHub

Usare una strategia a imbuto:

1. prima `search` mirato per simbolo, errore o filename;
2. poi leggere solo il file o le righe realmente rilevanti;
3. leggere file completi solo quando serve davvero il contesto intero;
4. non scaricare dump enormi di repository, issue o API list se bastano pochi risultati;
5. non ristampare nella chat interi risultati già conosciuti;
6. quando una ricerca non produce nulla di nuovo, annotare semplicemente che è stata verificata e non ha aggiunto evidenza;
7. riutilizzare i risultati già documentati in questo file invece di rifare le stesse query.

Per issue lunghe:
- leggere prima titolo, stato, date e ultimi commenti pertinenti;
- recuperare solo i commenti che aggiungono firmware, errori, workaround o conferme;
- evitare di riportare metadata GitHub inutili come avatar, reaction, URL API duplicati, node ID, ecc.

Per codice:
- cercare prima il simbolo;
- recuperare il blocco/righe circostanti;
- evitare di leggere interi file TypeScript/JavaScript se serve solo una dichiarazione o una funzione.

### Regola di efficienza per ricerca web

Per ricerche web pubbliche:

1. usare query molto specifiche con firmware, errore o nome API;
2. preferire fonti primarie: repository ufficiali, issue originali, documentazione, sorgenti;
3. non aprire molte pagine quasi equivalenti;
4. non accumulare risultati generici se non cambiano la diagnosi;
5. salvare nel context solo il contenuto utile, non il testo integrale delle pagine;
6. distinguere sempre tra:
   - fatto verificato sulla TV reale;
   - comportamento documentato in sorgente;
   - esperienza riportata da altri utenti;
   - ipotesi nostra.

### Budget pratico di ricerca

Prima di ampliare una ricerca, chiedersi:

> Questa nuova query può cambiare una decisione di implementazione o suggerire un test concreto?

Se la risposta è no, fermarsi.

Dopo 2-3 query mirate senza nuove evidenze sostanziali:
- non continuare a espandere automaticamente la ricerca;
- implementare il probe/runtime necessario;
- usare il risultato della TV reale come fonte prioritaria.

### Priorità delle fonti

Ordine di affidabilità per questo progetto:

1. risultati reali della Hisense `50E70LEVS_0003 / V0000.09.60A.Q0707`;
2. source JavaScript/runtime realmente esposto dalla stessa TV;
3. codice sorgente pubblico VIDAA/Hisense o wrapper direttamente rilevante;
4. issue/commenti con firmware e log concreti;
5. supposizioni generiche o comportamenti di firmware più vecchi.

Le fonti di livello inferiore non devono sovrascrivere evidenza concreta proveniente dalla TV.

### Obiettivo

La prossima AI deve poter leggere `AI_CONTEXT.md` e sapere:
- cosa è già stato cercato;
- quali fonti hanno dato risultati;
- quali query non hanno prodotto nulla;
- quali ipotesi sono ancora aperte;
- quale test implementare dopo.

Questo evita di spendere gran parte della chat a rifare ricerche GitHub/web già concluse.

---

## IMPLEMENTAZIONE — Permission & AppConfig Probe — 2026-09-25

Questa fase è stata implementata senza nuove ricerche web/GitHub: sono state riutilizzate le evidenze già documentate sopra.

### Stato implementato

La UI contiene ora un'azione separata chiamata "Permission & AppConfig Probe".

Il risultato sintetico mostra:
- completamento del probe;
- numero totale di entry interessanti raccolte;
- stato di Hisense_SupportAppConfig;
- presenza/assenza di vowOS;
- presenza/assenza di HiUtils_createRequest.

I dettagli completi vengono salvati in state.permissionProbe e quindi inclusi nei report JSON esistenti tramite saveReport("permission-appconfig-probe").

### Matcher runtime

enumerateInterestingGlobals() mantiene i matcher VIDAA/Hisense già utili e include anche:

- appconfig / appConfig
- permission / permissions
- access
- client
- whitelist
- domain
- origin
- security
- installApplication
- config
- capability
- privilege
- auth
- certificate
- signature
- sign
- vowOS
- hiutils
- Hisense_SupportAppConfig

L'enumerazione usa descriptor e non legge automaticamente il valore di accessor/getter globali.

### Introspezione sicura

Per gli oggetti ispezionati il probe può salvare:

- path completo;
- property name;
- tipo;
- valore primitivo per normali data property;
- enumerable;
- configurable;
- writable quando applicabile;
- presenza getter/setter;
- source getter/setter senza invocarli;
- source delle funzioni;
- riferimenti interessanti estratti dal source;
- info sul prototype;
- elenco di proprietà interessanti;
- errori di descriptor/property enumeration.

La traversal usa una coda iterativa e gestione circular reference; non usa recursion libera.

Limiti implementati:

- profondità massima: 3;
- massimo proprietà lette per oggetto: 80;
- massimo entry di proprietà totali: 700;
- massimo entry per root: 220;
- massimo global match: 320;
- stringhe: 1000 caratteri;
- function/getter/setter source: 5000 caratteri;
- proprietà prototype salvate: 50;
- source references: 50.

### Hisense_SupportAppConfig

Se è presente come normale data property e contiene una funzione, il probe:

1. salva descriptor e function source;
2. chiama Hisense_SupportAppConfig() senza parametri;
3. salva stato returned oppure error;
4. salva tipo/valore primitivo del risultato;
5. se il risultato è un oggetto, lo ispeziona con gli stessi limiti sicuri.

Se il simbolo globale fosse esposto tramite accessor, il probe registra l'accessor ma NON lo invoca.

### HiUtils_createRequest

Il probe salva descriptor, function source e riferimenti/stringhe interessanti estratti dal source.

Il Permission/AppConfig Probe NON chiama HiUtils_createRequest e non inventa/brute-forza nomi di API HiUtils.

Il fileRead di websdk/Appinfo.json rimane esclusivamente nella funzione di verification già esistente.

### vowOS

Se vowOS è disponibile come data property, il probe ispeziona in modo read-only l'oggetto e le sue proprietà, inclusi eventuali rami come vowOS.service, entro i limiti sopra.

Nessun metodo vowOS viene chiamato automaticamente.

### API security enumerate-only

Queste API vengono enumerate/ispezionate quando presenti, ma NON chiamate dal probe:

- Hisense_HiSdkSignCreate
- Hisense_HiSdkSignCreateSoundbar
- Hisense_HiSdkJsonVerifyHeap
- Hisense_CheckAccessCode
- Hisense_CheckCodeValid
- Hisense_GetRoleID
- Hisense_SetRoleID
- Hisense_GetCustomerID
- Hisense_SetCustomerID
- Hisense_Encrypt
- Hisense_Decrypt
- Hisense_RSADecrypt

In particolare non vengono eseguite API Set*, firma, access code, encrypt/decrypt, reset o write.

### Chiamate reali del nuovo probe

L'unica nuova funzione VIDAA che il Permission/AppConfig Probe può chiamare automaticamente è Hisense_SupportAppConfig(), e solo se è già esposta come normale data property function.

Il probe non esegue:
- getter/accessor sconosciuti;
- metodi vowOS;
- HiUtils_createRequest;
- install/uninstall;
- file write;
- reset;
- API Set*.

Il salvataggio del report usa soltanto il normale endpoint HTTP locale di Sidee già esistente.

### Compatibilità browser PC

In un browser PC senza API VIDAA il probe deve completare comunque:
- Hisense_SupportAppConfig: unavailable;
- vowOS: not found;
- HiUtils_createRequest: not found.

Nessuna API VIDAA è richiesta per completare la scansione.



---

## IMPLEMENTAZIONE — Session report unico + verification compact — 2026-09-25

Questa fase è stata implementata senza ripetere la ricerca VIDAA/AppConfig già documentata.

### Sessione diagnostica

Una pagina Sidee crea un solo `sessionId` nel formato:

`sidee-YYYYMMDD-HHMMSS-xxxx`

Lo stesso ID viene riutilizzato per scan, Permission/AppConfig Probe, target, install diagnostic, verification ed export.

Il filename non viene deciso dal browser. Il backend lo deriva esclusivamente dal session ID:

`sidee-session-YYYYMMDD-HHMMSS-xxxx.json`

### Endpoint report

Nuovo endpoint:

`POST /api/reports/session`

Payload:

- `sessionId`
- `report`

Il backend:

- valida con regex stretta `^sidee-\d{8}-\d{6}-[a-f0-9]{4}$`;
- non accetta filename/path dal client;
- deriva il filename server-side;
- verifica che il path risolto rimanga direttamente dentro `reports/`;
- scrive su un file temporaneo nella stessa directory;
- esegue flush + fsync;
- usa `os.replace` per l'update atomico;
- aggiorna sempre lo stesso file della sessione.

`POST /api/report` non genera più file legacy e risponde HTTP 410.

Restano invariati:

- `GET /api/reports/latest`
- `GET /api/reports`

### Struttura report

Il report principale contiene:

- `sessionId`
- `startedAt`
- `updatedAt`
- `summary`
- `environment`
- `permissionProbe`
- `target`
- `installDiagnostic`
- `verification`
- `raw.snapshots`

La `summary` viene aggiornata progressivamente e può contenere:

- firmware
- model
- OS
- apiVersion
- browser
- origin
- legacyAvailable
- v2Available
- getInstalledAppsAvailable
- appInfoReadable
- supportAppConfigAvailable
- supportAppConfigResult
- installRequest
- installApplicationRet
- permissionErrorCode
- permissionError
- verification
- conclusion

### Verification compact

`Hisense_getInstalledApps` e `websdk/Appinfo.json` non vengono più duplicati integralmente dentro ogni verifica.

La vista compact salva:

- count
- id
- name/title
- URL
- start command
- StoreType
- matchedTarget
- opzionalmente version/packageName quando presenti

Le raw complete, safe-serializzate e limitate, sono conservate al massimo una volta per snapshot significativo:

- `raw.snapshots.installedAppsBefore`
- `raw.snapshots.installedAppsAfter`
- `raw.snapshots.appInfoBefore`
- `raw.snapshots.appInfoAfter`

### Serializzazione robusta

Il salvataggio usa una serializzazione difensiva che gestisce:

- circular references
- functions
- `undefined`
- bigint/symbol
- `Error`
- accessor senza invocarli
- DOM/native objects problematici

I limiti di profondità, proprietà, entry, array e stringhe sono vincolati ai limiti già introdotti dal Permission/AppConfig Probe, così un runtime VIDAA anomalo non può far esplodere `JSON.stringify` o produrre copie illimitate.

### Autosave e log

Lo stesso report viene aggiornato:

- dopo Device Scan;
- dopo Permission/AppConfig Probe;
- dopo verification;
- dopo install diagnostic (successo, rifiuto, errore o timeout);
- quando viene salvato il target.

`Export Report` sincronizza soltanto l'ultima versione dello stesso file.

Il log TV ora usa risultati sintetici per scan, verification, HiUtils trace e install error; liste installed apps, Appinfo completo e Permission Probe completo restano nel report e non vengono stampati nel log.

### Compatibilità

Non sono stati modificati:

- DNS
- HTTPS
- certificate generation
- DNS forwarding

Il browser PC continua a funzionare anche senza API VIDAA: scan/verification riportano semplicemente le API come non disponibili.


### Validazione locale della fase session report

Prima del commit sono stati eseguiti test locali senza TV reale:

- `sidee.py` passa `compile(..., "exec")`;
- due scritture consecutive con lo stesso `sessionId` producono lo stesso path e lasciano esattamente un file JSON;
- la seconda scrittura sostituisce correttamente il contenuto della prima;
- casi di session ID con `../`, slash, prefisso errato o hex maiuscolo vengono respinti;
- dopo la scrittura atomica non restano file `.tmp`;
- `web/app.js` passa il parsing JavaScript;
- una simulazione browser PC con mock delle API VIDAA ha eseguito scan, deep verification, install legacy con trace `installApplication` code 503 ed export;
- tutti i salvataggi della simulazione hanno usato lo stesso `sessionId`;
- il report finale simulato contiene solo i quattro raw snapshot previsti;
- la verification contiene liste compact;
- il log TV simulato non contiene il dump completo delle installed apps;
- callback `0` + trace `ret:false/code:503` viene classificato `REJECTED`.

Questi test verificano la logica locale e il formato report. Il prossimo test sulla Hisense reale deve confermare il comportamento con i payload effettivi del firmware.


### Correzione session lifetime — 2026-09-25

Il `sessionId` viene ora conservato in `sessionStorage` e riutilizzato se rispetta la regex prevista. In questo modo un reload/navigazione nella stessa browser session continua a puntare allo stesso filename server-side invece di creare un nuovo ID.
