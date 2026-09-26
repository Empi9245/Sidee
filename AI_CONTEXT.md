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


---

## IMPLEMENTAZIONE — Install Diagnostic + Summary + UI TV — 2026-09-25

Questa fase conclude il refactor diagnostico richiesto. Non è stata rifatta ricerca VIDAA/AppConfig esterna: sono state riutilizzate esclusivamente le evidenze già documentate in questo file.

### Workflow finale

La UI TV è organizzata nell'ordine:

1. Device / Environment Scan
2. Permission & AppConfig Probe
3. Target App Configuration
4. Install Diagnostic
5. Verification
6. Export Report

La Summary è separata dal log ed è visibile in alto durante il workflow.

### Pulsanti principali

I pulsanti principali sono:

- `Device / Environment Scan`
- `Permission & AppConfig Probe`
- `Save Target`
- `Run Install Diagnostic`
- `Run Verification`
- `Export Report`

Legacy/V2 non sono più presentati come due possibili soluzioni equivalenti.

### Run Install Diagnostic

L'azione esplicita `Run Install Diagnostic` esegue:

1. snapshot before;
2. Legacy diagnostic;
3. verification;
4. V2 diagnostic;
5. verification;
6. summary finale;
7. aggiornamento dello stesso report di sessione.

Il Permission/AppConfig Probe non avvia mai automaticamente l'installazione.

### Classificazione install

Gli stati principali usati sono:

- `AVAILABLE`
- `REQUESTED`
- `REJECTED`
- `VERIFIED INSTALLED`
- `NOT INSTALLED`
- `UNKNOWN`

Regola fondamentale mantenuta:

- callback JavaScript `0` non significa successo;
- se non esiste verification positiva non viene mostrato SUCCESS;
- se il trace `installApplication` contiene `ret:false`, `code:503` e il messaggio AppConfig permission check, la richiesta viene classificata `REJECTED`;
- in quel caso la Summary normalizza la reason a `APP CONFIG PERMISSION CHECK FAILED` e mostra permission code `503`;
- l'unico successo finale è `VERIFIED INSTALLED`.

### Summary TV

La Summary mostra:

- Environment, per esempio VIDAA / API version;
- Origin;
- Install API;
- AppConfig Probe;
- Install Request;
- Internal reason;
- Permission code;
- Verification.

Si aggiorna durante scan, probe, install diagnostic e verification. Il risultato principale non dipende dal log.

### Advanced diagnostics

Dentro `Advanced diagnostics` sono stati spostati:

- `Legacy only`;
- `V2 only`;
- `Uninstall`;
- compact log.

Uninstall non viene mai eseguito automaticamente.

### D-pad / telecomando

La navigazione non usa più il semplice ordine globale di `button,input`.

Usa i rettangoli reali dei controlli visibili:

- Up/Down sceglie il controllo spazialmente più vicino sopra/sotto;
- Left/Right sceglie il controllo più vicino a sinistra/destra;
- Enter/OK attiva button e summary;
- nei campi input Left/Right resta disponibile per muovere il cursore di testo;
- i controlli nascosti dentro Advanced chiuso non entrano nella navigazione;
- mouse e tastiera PC continuano a funzionare.

Il focus è stato reso molto più evidente e i controlli sono più grandi, con una scala ulteriore su viewport 4K.

### Log

Il log è collassato dentro Advanced diagnostics e usa messaggi sintetici, per esempio:

- `Device scan complete — N VIDAA APIs`
- `Permission probe — N relevant runtime entries`
- `Hisense_SupportAppConfig — returned/...`
- `Legacy install — rejected (503)`
- `V2 install — rejected (503)`
- `Verification — target not found`

I dettagli completi restano nel JSON.

### Report

Rimane un solo report aggiornabile per sessione:

`sidee-session-YYYYMMDD-HHMMSS-xxxx.json`

`Export Report` sincronizza la sessione corrente e la UI mostra il filename corrente.

### Target

Il target resta configurabile con:

- app ID;
- nome;
- URL;
- icon URL.

I default correnti restano `nuviodebug` / `Nuvio TV`, ma nessun IP LAN viene hardcodato nel frontend.

### Server / sicurezza

Non sono stati cambiati DNS, HTTPS, certificate generation o DNS forwarding.

Restano vietati/assenti dal workflow automatico:

- `fileWrite`;
- write diretto di Appinfo;
- install automatico dopo Permission Probe;
- uninstall automatico;
- reset / Set* / metodi security state-changing.

### Test reale da fare sulla Hisense

1. avvia Sidee sul PC;
2. imposta DNS TV sul PC;
3. apri `https://vidaahub.com`;
4. premi `Device / Environment Scan`;
5. premi `Permission & AppConfig Probe`;
6. controlla Summary;
7. configura target se necessario;
8. premi `Run Install Diagnostic`;
9. lascia completare Legacy + V2 + verification;
10. premi `Export Report`;
11. prendi il singolo JSON nella cartella `reports`;
12. usa quel report come input della chat successiva.

---

## IMPLEMENTAZIONE — Client Identity / Permission Context Probe — 2026-09-25

Questa fase è stata implementata senza nuove ricerche web o issue GitHub esterne. Usa esclusivamente il runtime già esposto dalla TV e le evidenze documentate sopra.

### Nuovo step read-only

Il workflow TV è ora:

1. Device / Environment Scan
2. Permission & AppConfig Probe
3. Client Identity Probe
4. Target App Configuration
5. Install Diagnostic
6. Verification
7. Export Report

Il Client Identity Probe è separato dall'installazione e non avvia alcun tentativo di install.

### API realmente chiamate dal Client Identity Probe

Solo quando esposte come normali data-property function, senza invocare accessor/getter sconosciuti:

- `vowOS.service.getIdentifier()`
- `vowOSContext.getAppIdentifier()`
- `vowOSContext.getAppId()`
- `Hisense_GetRoleID()`
- `Hisense_GetCustomerID()`

Per ogni chiamata vengono salvati status, tipo, valore ed eventuale errore.

`clientInformation` resta inspect-only: Sidee salva descriptor e getter source, ma non invoca l'accessor.

Restano non chiamati dal nuovo probe:

- `Hisense_SetRoleID`
- `Hisense_SetCustomerID`
- `Hisense_HiSdkSignCreate`
- `Hisense_HiSdkSignCreateSoundbar`
- `Hisense_HiSdkJsonVerifyHeap`
- `Hisense_CheckAccessCode`
- `Hisense_CheckCodeValid`
- encrypt/decrypt/RSA
- fileWrite/Appinfo write
- reset
- uninstall
- API HiUtils inventate o sconosciute.

### Report

Il report di sessione contiene ora:

- `clientIdentityProbe`
- `hiUtilsTrace`

`clientIdentityProbe` salva i valori correnti di service identifier, app identifier, app ID, Role ID e Customer ID, più il descriptor inspect-only di `clientInformation`.

Il probe calcola anche, solo quando entrambi i valori sono realmente disponibili, se service identifier e app identifier coincidono. Questa comparazione non viene interpretata come prova che l'identifier sia la chiave AppConfig.

### Correlazione HiUtils

Ogni entry HiUtils catturata durante gli install diagnostic include uno snapshot `clientContext` con:

- serviceIdentifier
- appIdentifier
- appId
- roleId
- customerId

Anche il `fileRead` read-only di `websdk/Appinfo.json` registra una entry compatta nel trace di sessione con lo stesso `clientContext`.

I risultati del trace di sessione sono volutamente compatti: per evitare duplicazioni del contenuto Appinfo vengono conservati ret/code/message e il contesto identità, mentre i raw snapshot restano nella sezione `raw.snapshots` già esistente.

Ogni tentativo Legacy/V2 salva inoltre `clientContextBefore` e `clientContextAfter`, così il prossimo report può mostrare se l'identità cambia prima/dopo un install attempt.

### Cosa deve verificare il prossimo report reale TV

Il prossimo JSON deve permettere di confrontare:

1. valore reale di `vowOS.service.getIdentifier()`;
2. valore reale di `vowOSContext.getAppIdentifier()`;
3. eventuale uguaglianza tra i due;
4. valore reale di `vowOSContext.getAppId()`;
5. Role ID e Customer ID correnti;
6. clientContext del `fileRead` consentito;
7. clientContext di `installApplication` Legacy e V2;
8. eventuali differenze Legacy/V2;
9. eventuali variazioni before/after;
10. presenza del consueto 503 AppConfig a parità di identity.

Interpretazione corretta se fileRead e installApplication usano la stessa identity ma il primo passa e il secondo viene respinto: forte evidenza di permission per-API associata al client corrente. Non è prova di un bypass e non autorizza modifiche a role/customer/signature.



---

## IMPLEMENTAZIONE — Runtime Identity / navigator.appIdentifier — 2026-09-25

Questa fase parte dal report reale in cui:

- `vowOS.service.getIdentifier() === ""`;
- `vowOSContext.getAppIdentifier() === ""`;
- `vowOSContext.getAppId() === ""`;
- Role ID / Customer ID sono null;
- `fileRead("websdk/Appinfo.json")` passa;
- `installApplication` fallisce con code 503 AppConfig permission check.

### Ricerca esterna mirata

È stata fatta solo la ricerca mirata richiesta su:

- `navigator.appIdentifier`;
- `vowOSContext.init`;
- `vowOSContext.getAppIdentifier`;
- `vowOSContext.getAppId`;
- `clientInformation`;
- VIDAA odin/browser app identity.

Non è stata trovata una implementazione pubblica affidabile di `vowOSContext.init()` o del lifecycle VIDAA che assegna `navigator.appIdentifier`. Quindi NON è stato aggiunto alcun tentativo di `init()` e non sono stati inventati parametri.

Nuova evidenza web standard utile:

- MDN / HTML Window API documentano `Window.clientInformation` come alias legacy read-only di `Window.navigator`.
- Riferimenti: https://developer.mozilla.org/docs/Web/API/Window e https://html.spec.whatwg.org/multipage/nav-history-apis.html#the-window-object

Implicazione concreta: leggere manualmente `window.clientInformation` una volta è una normale lettura informativa del browser; non è una prova di privilege VIDAA e non autorizza l'uso di setter.

### Runtime Identity Probe

Il vecchio Client Identity Probe è stato esteso/rinominato in UI come `Runtime Identity Probe`.

Salva nello stesso report di sessione:

- `runtimeIdentityProbe.navigatorAppIdentifier`;
- descriptor di `navigator.appIdentifier`;
- owner/prototype depth;
- getter/setter source senza invocare setter;
- proprietà Navigator correlate a app/identifier/client/context/VIDA/vow;
- source di `vowOS.service.getIdentifier`;
- struttura completa limitata di `vowOSContext`;
- descriptor/source di `getAppIdentifier`, `getAppId`, `init`;
- lifecycle/source references interessanti;
- snapshot identity già esistente (serviceIdentifier/appIdentifier/appId/roleId/customerId);
- metadata `clientInformation`.

### Lettura navigator.appIdentifier

Sidee NON invoca alla cieca un accessor `navigator.appIdentifier`.

Regola:

- se è una data property, salva il valore dal descriptor;
- se è un accessor, lo legge una sola volta solo quando il source runtime di `vowOS.service.getIdentifier` dimostra concretamente che il normale path VIDAA legge `navigator.appIdentifier`;
- altrimenti resta inspect-only.

Questo evita getter sconosciuti e usa come evidenza prioritaria il source della TV reale.

### vowOSContext.init

`vowOSContext.init` viene ispezionato ma NON chiamato.

Il report contiene:

- availability;
- descriptor;
- function source se disponibile;
- declared argument count;
- references interessanti;
- `called:false`;
- `manualCallEligible:false`.

`runtimeContextInitialization` resta con `called:false` e `eligible:false` finché il prossimo report reale non dimostra source/argomenti/side effect sufficientemente chiari.

### clientInformation

È stato aggiunto un pulsante manuale:

`Read Client Information`

Fa una sola lettura di:

`window.clientInformation`

e salva:

- status;
- type;
- `sameAsNavigator`;
- valore safe-serializzato con limiti già esistenti;
- descriptor/getter/setter source.

Il setter non viene mai chiamato.

### Gate install diagnostic

Per rispettare il risultato già dimostrato e non ripetere tentativi inutili:

- `Run Install Diagnostic`;
- `Legacy only`;
- `V2 only`

sono ora bloccati finché Runtime Identity non trova almeno un valore non vuoto tra:

- `navigator.appIdentifier`;
- `serviceIdentifier`;
- `appIdentifier`;
- `appId`.

Se tutti restano vuoti, Sidee salva il motivo del blocco nel report e NON esegue Legacy/V2.

Se compare una vera identity, il workflow install già esistente resta disponibile e continua a fare verification + HiUtils trace + classificazione 503 corretta.

### Vincoli di sicurezza mantenuti

Questa fase NON chiama:

- `Hisense_SetRoleID`;
- `Hisense_SetCustomerID`;
- setter `clientInformation`;
- setter `navigator.appIdentifier`;
- `Hisense_HiSdkSignCreate*`;
- access-code/security API;
- fileWrite/Appinfo write;
- reset;
- `vowOSContext.init()`;
- install automatico dopo il probe.

### Prossimo test reale TV

Eseguire:

1. Device / Environment Scan;
2. Permission & AppConfig Probe;
3. Runtime Identity Probe;
4. opzionale: Read Client Information;
5. Export Report.

Prima di premere install, leggere il report e verificare soprattutto:

- descriptor/value reale di `navigator.appIdentifier`;
- source reale di `vowOS.service.getIdentifier`;
- source/arity reale di `vowOSContext.init`;
- eventuali funzioni lifecycle trovate dentro `vowOSContext`;
- `clientInformation.sameAsNavigator`;
- eventuale comparsa di una identity non vuota.

Se identity resta vuota, NON serve ripetere install. Se compare, Sidee sblocca il test install controllato.


---

## HARDENING — Runtime Identity gates — 2026-09-25

Il commit precedente aveva già introdotto Runtime Identity, il gate install e l'ispezione di `navigator.appIdentifier`. Questa rifinitura corregge tre punti prima del test TV successivo.

### clientInformation: vendor runtime prima del web generico

La documentazione web standard su `Window.clientInformation` non viene più considerata sufficiente, da sola, per leggere il getter sulla Hisense.

Motivo: sul firmware reale la proprietà è un accessor nativo con getter E setter. Quindi Sidee tratta l'implementazione vendor come fonte prioritaria.

Il pulsante `Read Client Information` è ora nascosto salvo:

- data property normale; oppure
- getter presente + source ispezionato di `vowOSContext` che mostra una normale lettura di `clientInformation`.

La lettura è one-shot per page session. Il setter non viene mai usato.

### vowOSContext.init: gate dinamico e conservativo

`init()` resta non automatico.

Il pulsante `Initialize Runtime Context` compare solo se il source reale supera un gate stretto:

- funzione disponibile come data property;
- source completo, non nativo e non troncato;
- declared argument count = 0;
- firma zero-argument esplicita;
- riferimenti concreti a identity/context;
- nessun riferimento a HiUtils/syncExecute, API Hisense native, install/uninstall, file write, role/customer setter, signing/security, reset, rete, navigation o storage write.

Se il gate passa, il click manuale chiama `init()` una sola volta e salva:

- before;
- returnValue;
- after;
- changedFields.

Non parte alcun install automatico dopo init.

### HiUtils trace

`captureTraceClientContext()` include ora anche:

`navigatorAppIdentifier`

oltre a serviceIdentifier/appIdentifier/appId/roleId/customerId.

### Report

La duplicazione `clientIdentityProbe` è stata rimossa dal nuovo report di sessione. La fonte principale diventa:

- `runtimeIdentityProbe`;
- `runtimeContextInitialization`.

### Ricerca

Nessuna nuova ricerca esterna è stata aggiunta in questa rifinitura: le query mirate della fase precedente non avevano trovato source pubblici utili per il lifecycle VIDAA. La prossima evidenza decisiva deve arrivare dal report reale della TV.


---

## FINAL HARDENING — Runtime Identity evidence persistence — 2026-09-25

Questa rifinitura parte da `3cbe0914de8472c1fc03646607928d7e044e4a8a` e non cambia la strategia di sicurezza.

### Evidenza clientInformation preservata

È stato corretto un caso in cui:

1. l'utente eseguiva il read manuale one-shot di `clientInformation`;
2. il valore veniva salvato correttamente;
3. un successivo Runtime Identity Probe ricostruiva un record inspect-only e poteva perdere dal report il valore letto.

Ora il risultato manuale viene mantenuto in memoria della page session e riapplicato ai successivi snapshot Runtime Identity. Il setter resta sempre non chiamato.

### Ricerca riferimenti runtime più completa

La ricerca read-only dei riferimenti a `clientInformation` considera ora:

- source delle normali funzioni;
- source dei getter ispezionati;
- funzioni rilevanti dentro `vowOSContext`;
- globali VIDAA/Hisense già selezionati dal matcher del Permission Probe.

Questo non invoca gli accessor: serve solo a decidere se mostrare il pulsante manuale di lettura.

### Runtime identity assessment

`runtimeIdentityProbe.assessment` sintetizza ora:

- `IDENTITY PRESENT` se compare almeno un app identity signal non vuoto;
- `ANONYMOUS-LIKE` quando serviceIdentifier/appIdentifier/appId sono realmente ritornati vuoti e Role/Customer sono null;
- `INCOMPLETE` quando i dati non bastano.

Salva inoltre esplicitamente:

- installRetestEligible;
- identitySignals;
- emptyReturnedSignals;
- se il source di service identifier passa da navigator.appIdentifier;
- stato/sicurezza di vowOSContext.init;
- evidenza runtime per clientInformation;
- `identityAssignmentSource: NOT PROVEN`;
- `launcherOrBrowserAssignment: NOT PROVEN`;
- domande lifecycle ancora aperte.

Quindi Sidee non trasforma una forte ipotesi in un fatto.

### Timeout init asincrono

Se il rarissimo gate stretto rende disponibile il test manuale di `vowOSContext.init()` e la funzione restituisce un Promise/thenable, Sidee attende al massimo 2000 ms.

Il timeout:

- non richiama init;
- non esegue fallback;
- non avvia install;
- consente comunque di acquisire lo snapshot AFTER e registrare l'errore/timeout.

### Ricerca esterna verificata in questa fase

Le code search GitHub esatte per:

- `"navigator.appIdentifier" VIDAA`;
- `"vowOSContext.init"`;
- `"getAppIdentifier" vowOSContext`;

hanno restituito 0 risultati pubblici utili.

MDN continua a documentare `Window.clientInformation` come alias read-only di `Window.navigator`, ma per Sidee questa evidenza web generica NON basta da sola a leggere l'accessor vendor Hisense: il gate runtime introdotto nel commit precedente resta prioritario.

### Validazione locale richiesta

La versione finale è stata verificata con:

- parsing JavaScript;
- harness browser PC senza API VIDAA: Runtime Identity completa senza crash;
- mock `navigator.appIdentifier` data property;
- mock `vowOS.service.getIdentifier`;
- mock `vowOSContext.getAppIdentifier/getAppId`;
- mock `vowOSContext.init` zero-argument: non parte automaticamente e viene chiamato una sola volta solo dal pulsante manuale;
- mock `clientInformation` accessor con getter/setter: getter non invocato dal probe, setter mai invocato, lettura manuale one-shot;
- rerun Runtime Identity dopo lettura clientInformation: evidenza manuale preservata;
- nessuna nuova chiamata a Role/Customer setter, firma/security, fileWrite o install automatico.

Il prossimo passo utile resta il test sulla Hisense reale e l'analisi del singolo report di sessione.


---

## TARGETED VIDAA IDENTITY / APPCONFIG DIAGNOSTIC — 2026-09-26

Il report reale `sidee-session-20260926-104537-d029` ha dimostrato che il summary precedente produceva un falso positivo: `runtimeIdentity: IDENTITY PRESENT` e `identityGate: UNLOCKED` non erano supportati dai valori runtime.

Valori reali osservati:

- `navigator.appIdentifier = "undefined"`;
- `vowOS.service.getIdentifier() = ""`;
- `vowOSContext.getAppIdentifier() = ""`;
- `vowOSContext.getAppId() = ""`;
- `Hisense_GetRoleID() = null`;
- `Hisense_GetCustomerID() = null`.

La classificazione corrente usa quindi `MISSING / PARTIAL / PRESENT`: `PRESENT` richiede almeno un identifier/app ID realmente non vuoto. Il permission gate usa `UNKNOWN / REJECTED / CHANGED / PASSED` e non viene più considerato sbloccato per la sola presenza delle API.

La pista principale resta il servizio locale VIDAA: `HiUtils_createRequest(...)` passa attraverso `vowOS.service.syncExecute(...)`; il servizio usa endpoint localhost (osservati nelle analisi precedenti, ad esempio porte 9888/9009) e l'header `identifier` deriva da `vowOS.service.getIdentifier()`. Nel report reale l'identifier è ancora vuoto e `installApplication` viene respinto dal permission check AppConfig con code 503.

Il nuovo workflow non esegue più scansioni globali o dump estesi. Salva soltanto device compatto, baseline identity, risultato reale di `vowOSContext.init()`, diff prima/dopo, `clientInformation` filtrato, service trace compatto, install permission test e summary.

`vowOSContext.init()` viene ora chiamato realmente anche se nativo, con gestione sync/Promise/callback e timeout. Prima e dopo vengono confrontati appIdentifier, appId, service identifier, Role, Customer e clientInformation.

`window.clientInformation` viene letto tramite getter e salvato in forma compatta; il descriptor registra getter/setter ma il setter non viene mai chiamato automaticamente. `Hisense_SetRoleID` e `Hisense_SetCustomerID` vengono soltanto segnalati come disponibili/non disponibili e non sono esposti nel workflow standard.

La service instrumentation è temporanea e reversibile: prova a tracciare `getIdentifier`, `syncExecute`, `HiUtils_createRequest` e l'eventuale URL localhost osservato via XHR; ogni wrapper viene ripristinato in `finally`.

È disponibile anche `Temporary Identifier Test`, separato e manuale: richiede un valore esplicito, sostituisce temporaneamente `vowOS.service.getIdentifier()`, esegue una sola richiesta read-only a `websdk/Appinfo.json` e ripristina sempre la funzione originale. Nessun brute force.

Il test install resta esplicito. Il callback esterno `0` non viene interpretato come successo: contano il risultato interno `installApplication` e la verifica dell'app installata.

### Prossimo test TV

Eseguire nell'ordine: Baseline → Initialize Context → controllare il diff → Read Client Information → Trace Read-only Service Request → Test Install Permission → Export/Sync Report.

Nel prossimo report sono particolarmente importanti: se `vowOSContext.init()` cambia uno degli identifier, il contenuto filtrato di `clientInformation`, l'identifier realmente visto dal service trace, l'endpoint localhost se osservabile e l'eventuale variazione di ret/code/msg del permission check.

---

## IMPLEMENTAZIONE — Installed App Metadata Inspector — 2026-09-26

È stato aggiunto un `Installed App Metadata Inspector` per confrontare, senza modifiche runtime o filesystem scan, i metadata già esposti dalle app installate. La motivazione è il risultato reale in cui `fileRead("websdk/Appinfo.json")` passa con identifier vuoto mentre `installApplication` viene respinto con `ret:false`, code `503` e permission check AppConfig: questo è compatibile con un controllo permission/ACL per API, ma non viene trattato come prova definitiva.

Le uniche fonti usate dall'Inspector sono `Hisense_getInstalledApps` e `HiUtils_createRequest("fileRead", { path: "websdk/Appinfo.json", mode: 6 })`. I record vengono normalizzati in forma compatta, associati prima per ID/appId/unifiedAppName, poi URL/startCommand e infine nome/title. Il report salva per ogni app identità compatta, dati normalizzati per fonte, sorgenti matched, metadata interessanti e classificazione descrittiva `store / hisense / preinstalled / unknown`.

L'ispezione considera i campi core richiesti (ID, nome, URL/start command, StoreType/openMode/vendor, unifiedAppName, config/package/version/developer/category/preInstall/launcher) e proprietà correlate a permission, privilege, security, appconfig/config, identifier/client, role/customer, origin/domain, package/bundle, store/install/launch, sign/certificate/auth. La scansione dei singoli record è limitata a profondità 3, massimo 40 proprietà interessanti per app e stringhe di circa 500 caratteri; immagini, base64/blob e contenuti promozionali voluminosi vengono esclusi.

Il report di sessione unico contiene `installedAppMetadata` con `sources`, `apps`, `fieldDistribution`, `discoveredReferences` e `summary`. I riferimenti path/config già presenti nei metadata vengono soltanto registrati; non vengono letti automaticamente. Un rerun sostituisce la sezione precedente invece di accumulare duplicati.

Vincoli mantenuti: nessun directory traversal, path guessing, filesystem scan, fileWrite, install/uninstall automatico, Role/Customer setter, clientInformation setter, API security/signature o reset. Il prossimo report reale deve mostrare quali campi espone ciascuna fonte, quali app fanno match, distribuzioni tra store/hisense/preinstalled/unknown, eventuali campi permission/AppConfig/security/identifier/client/role e riferimenti config/path concreti da valutare in una fase successiva.

---

## TEST REALE — Installed App Metadata Inspector parsing fix — 2026-09-26

Il report reale `sidee-session-20260926-104537-d029` ha confermato che `Hisense_getInstalledApps` restituisce 61 record e che il `fileRead` di `websdk/Appinfo.json` passa ancora con identifier vuoto (`ret:true`, `code:0`). Tuttavia la prima versione dell'Inspector riportava erroneamente `appInfoCount: 0` e `matchedCount: 0`.

Root cause: `Appinfo.json` arriva nel campo `msg` come stringa JSON. Il collector incrementava la profondità una volta entrando nel campo `msg` e una seconda volta durante il parse della stringa JSON; gli oggetti dentro `AppInfo[]` arrivavano così a depth 4 e venivano esclusi dal limite depth 3. Il parse JSON ora non consuma un livello strutturale e il child già parsato viene passato direttamente al collector.

Il report reale ha inoltre mostrato `StoreType` numerico 98/99/100 nella fonte `Hisense_getInstalledApps`, mentre i metadata più ricchi di `Appinfo.json` non erano ancora stati estratti a causa del bug sopra. La classificazione `store / hisense / preinstalled / unknown` resta quindi basata solo su valori testuali reali quando presenti; i codici numerici non vengono interpretati/inventati.

È stata corretta anche la `fieldDistribution`: i campi normalizzati e i corrispondenti metadata raw con differenze solo di maiuscole/minuscole non vengono più contati due volte (nel report precedente `isShowOnLauncher:true` risultava 122 su 61 app).

Il prossimo test TV deve rieseguire soltanto `Inspect Installed Apps` e poi `Export Report`. Il risultato atteso è `appInfoCount > 0`, match per ID con almeno le app presenti in entrambe le fonti, metadata Appinfo come StoreType/openMode/venderId/unifiedAppName/configUrl e distribuzioni senza duplicazione.


---

## IMPLEMENTAZIONE — AppInfo Deep Dump read-only — 2026-09-26

Dopo il report reale `sidee-session-20260926-104537-d029` (61 InstalledApps, 3 AppInfo, 3 match), l'Installed App Metadata Inspector è stato esteso senza aggiungere nuovi path o nuove API.

La stessa lettura read-only già verificata:

`HiUtils_createRequest('fileRead', { path: 'websdk/Appinfo.json', mode: 6 })`

ora conserva anche i record AppInfo originali completi nel report sotto:

`installedAppMetadata.appInfoDeepDump`

Struttura:
- `path`
- `readOnly: true`
- `recordCount`
- `records`

`records` contiene gli oggetti AppInfo originali usati dall'Inspector, senza filtraggio dei campi, normalizzazione o truncation applicata a questa copia. Restano quindi presenti anche valori vuoti e gli oggetti annidati `appInfo` / `showInfo` quando esistono.

La vista compatta/normalizzata precedente (`apps`, `fieldDistribution`, `discoveredReferences`, `summary`) è mantenuta invariata per il confronto.

Nessuna modifica è stata fatta a install/uninstall, fileWrite, permission test, Role/Customer setter o path discovery.

Prossimo test TV: eseguire soltanto **Inspect Installed Apps** e poi **Export Report**. Nel nuovo JSON controllare in particolare `installedAppMetadata.appInfoDeepDump.records` per package/bundle/identifier/manifest/config/permission/security/signature/auth metadata che la vista normalizzata potrebbe non evidenziare.


---

## IMPLEMENTAZIONE — Permission Source Trace + verification counts — 2026-09-26

Il Deep Dump reale di `websdk/Appinfo.json` ha chiuso la pista AppInfo come fonte primaria del permission gate: i 3 record completi espongono metadata di catalogo/launcher/store (`openMode`, `venderId`, `unifiedAppName`, `configUrl`, `appBundle`, `packaged`) ma nessun campo permission/privilege/security/appconfig/identifier/client/role/customer/auth/certificate/signature. `configUrl` e `appBundle` risultano vuoti nei record osservati.

È stato quindi aggiunto un nuovo step UI/read-only: **Install Permission Source Trace**.

Il trace ispeziona senza invocare install/uninstall:
- `Hisense_installApp`
- `Hisense_installApp_V2`
- `HiUtils_createRequest`
- `Hisense_SupportAppConfig`
- `vowOS.service.syncExecute`
- `vowOS.service.getIdentifier`

Per ogni funzione salva:
- availability/type
- descriptor
- name/arity
- `Function.prototype.toString()`
- riferimenti concreti trovati nel source relativi a permission/appconfig/identifier/client/role/customer/origin/package/bundle/auth/security/sign/certificate/access/capability/privilege/config/installApplication/HiUtils.

`Hisense_SupportAppConfig()` senza parametri resta l'unica funzione diagnostica invocata da questo nuovo step, coerentemente con il probe read-only già approvato. Non vengono chiamate API HiUtils inventate, path dedotti, install/uninstall, fileWrite o setter.

Il report salva il risultato in:
`permissionSourceTrace`

È stato corretto anche il conteggio della verification. Il vecchio collector generico contava oggetti annidati e nel report reale poteva mostrare valori come 52 InstalledApps / 5 AppInfo mentre l'Inspector corretto trovava 61 / 3. Ora verification usa lo stesso parsing app-record-aware dell'Installed App Metadata Inspector, quindi `count` rappresenta record applicazione deduplicati e il match target viene eseguito sugli stessi record reali.

Prossimo test TV consigliato:
1. Capture Baseline (se nuova sessione)
2. **Trace Permission Sources**
3. Run Verification
4. Export Report

Non serve ripetere un install test per ottenere il Source Trace.


---

## IMPLEMENTAZIONE — Install pipeline helper source trace — 2026-09-26

Il Source Trace reale ha esposto il codice dei wrapper VIDAA:
- `Hisense_installApp`
- `Hisense_installApp_V2`
- `HiUtils_createRequest`
- `Hisense_SupportAppConfig`
- `vowOS.service.syncExecute`
- `vowOS.service.getIdentifier`

Il codice reale mostra che i wrapper install non chiamano direttamente `installApplication`: entrambi passano l'intero registro `AppInfo` a `writeInstallAppObjToJson(installAppObj)`. Inoltre `HiUtils_createRequest(type,msg)` è solo un wrapper di `vowOS.service.syncExecute('hiutils',{api:type,args:msg})`, mentre `getIdentifier()` restituisce `vowOSContext.getAppIdentifier()` solo se `navigator.appIdentifier !== 'undefined'`, altrimenti restituisce stringa vuota.

Per seguire la catena senza eseguire nuove operazioni, il Permission Source Trace è stato esteso ai quattro helper concreti appena rivelati:
- `window.writeInstallAppObjToJson`
- `window.getInstalledAppJsonObj`
- `window.mapAppInfoFields`
- `window.vowOS.service.executeHttpRequest`

Questi helper vengono soltanto ispezionati tramite descriptor e `Function.prototype.toString()`; non vengono invocati.

Il filtro dei riferimenti concreti ora include anche:
- `installApplication`
- `executeHttpRequest`
- `fileRead`
- `fileWrite`
- `AppInfo`
- i nomi dei tre helper AppInfo sopra

Obiettivo del prossimo report: ricostruire precisamente `Hisense_installApp[_V2] -> writeInstallAppObjToJson -> HiUtils_createRequest -> syncExecute -> executeHttpRequest` e verificare se l'HTTP executor aggiunge identifier/header/client metadata alla richiesta localhost.

Per questo test non serve eseguire un nuovo install test: basta **Trace Permission Sources** seguito da **Export Report**.


---

## IMPLEMENTAZIONE — Loaded Script Source Trace — 2026-09-26

Il report reale successivo ha confermato il confine del permission gate:
- `writeInstallAppObjToJson(AppJsonObj)` serializza l'intero registro AppInfo e chiama `HiUtils_createRequest('installApplication', writedata)`;
- `vowOS.service.executeHttpRequest(url,args)` invia una POST al servizio localhost e imposta esplicitamente l'header HTTP `identifier` con `this.getIdentifier()`;
- `vowOS.service.getIdentifier()` restituisce `vowOSContext.getAppIdentifier()` solo quando `navigator.appIdentifier !== 'undefined'`, altrimenti restituisce stringa vuota;
- nel contesto Sidee l'identifier osservato resta vuoto.

Per cercare da dove VIDAA normalmente popola l'identità client/AppConfig senza eseguire nuove API, il Permission Source Trace ora include anche un inventario read-only di `document.scripts`.

Comportamento:
- enumera fino a 80 script già caricati;
- per script inline legge soltanto `textContent`;
- per script esterni esegue solo una GET sullo stesso URL se è same-origin;
- script cross-origin vengono elencati ma non letti;
- `/app.js` di Sidee viene elencato ma escluso dalla scansione per evitare falsi positivi creati dal codice diagnostico stesso;
- nessun sorgente recuperato viene eseguito o modificato.

Termini cercati:
- `mapAppInfoFields`
- `appIdentifier`
- `getAppIdentifier`
- `AppConfig`
- `permission`
- `identifier`
- `client`
- `service`
- `vowOSContext`
- `getIdentifier`
- `executeHttpRequest`
- `installApplication`
- `HiUtils_createRequest`

Il report salva i risultati in:
`permissionSourceTrace.loadedScripts`

Per ogni script vengono salvati URL/indice/tipo, stato della lettura, same-origin, lunghezza sorgente, termini trovati ed estratti contestuali limitati attorno ai match. Non viene salvato l'intero bundle per evitare report enormi.

Obiettivo del prossimo test TV: eseguire soltanto **Trace Permission Sources** e poi **Export Report**. Cercare in particolare `loadedScripts.entries` per definizioni di `mapAppInfoFields`, inizializzazione di `navigator.appIdentifier` / `vowOSContext`, riferimenti ad AppConfig/permission/client identity e codice che precede `getIdentifier`.


---

## IMPLEMENTAZIONE — Runtime Identity Surface Trace — 2026-09-26

La scansione `document.scripts` reale ha mostrato un solo script: `https://vidaahub.com/app.js` (Sidee stesso). Non risultano normali bundle VIDAA nel DOM; le API `Hisense_*`, `vowOS` e `vowOSContext` sono quindi trattate come superfici runtime/native-injected e non come codice recuperabile da normali tag script.

Per seguire direttamente la sorgente dell'identità client senza eseguire nuove API, il Permission Source Trace ora salva anche:

`permissionSourceTrace.runtimeIdentitySurface`

Il probe è completamente read-only e raccoglie descriptor + source senza invocare getter/setter/init/metodi scoperti.

Target esatti:
- `navigator.appIdentifier`
- `vowOSContext.getAppIdentifier`
- `vowOSContext.getAppId`
- `vowOSContext.init`
- `vowOS.service.getIdentifier`

Per ogni proprietà viene cercato il descriptor lungo la prototype chain fino a 7 livelli e vengono salvati:
- ownerDepth
- enumerable/configurable/writable
- presenza getter/setter
- tipo del data descriptor
- valore solo se scalare
- source della funzione se il descriptor contiene una function
- source di getter/setter se presenti

In più vengono enumerate in modo filtrato le proprietà proprie + prototype di:
- `window.vowOSContext`
- `window.vowOS.service`

Filtro nomi:
`app | identifier | client | config | permission | context | role | customer | auth | security | service | origin`

Per le proprietà filtrate vengono salvati soltanto descriptor e source associati. Nessun getter viene letto tramite accesso proprietà; nessun setter viene usato; `vowOSContext.init` non viene richiamato da questo probe; nessun eventuale `setIdentifier` o setter scoperto viene invocato.

Obiettivo del prossimo test TV: eseguire solo **Trace Permission Sources** e **Export Report**. Analizzare:
- `permissionSourceTrace.runtimeIdentitySurface.exact`
- `permissionSourceTrace.runtimeIdentitySurface.surfaces.vowOSContext`
- `permissionSourceTrace.runtimeIdentitySurface.surfaces.vowOSService`

Cercare in particolare source/descriptor che mostrino inizializzazione dell'app identity, eventuali setter/config methods, accesso ad AppConfig/client context o condizioni che spiegano perché `getAppIdentifier()` resta vuoto.


---

## IMPLEMENTAZIONE — Complete Runtime Bridge Inventory — 2026-09-26

Il Runtime Identity Surface Trace reale ha mostrato:
- `navigator.appIdentifier` come accessor nativo sul prototype, con getter `[native code]` e senza setter;
- `vowOSContext.getAppIdentifier`, `getAppId` e `init` come funzioni native;
- nessun setter/permission/config method evidente nella superficie filtrata di `vowOSContext`;
- nella superficie filtrata di `vowOS.service` soltanto `getIdentifier` e `reLaunchService`;
- `reLaunchService()` comunica con il runtime tramite `omi_platform.sendPlatformMessage(...)`.

Per evitare che il filtro per nome nasconda metodi con nomi non ovvi, il Permission Source Trace ora salva anche un inventario completo e non filtrato:

`permissionSourceTrace.runtimeObjectInventory`

Oggetti inventariati:
- `window.vowOSContext`
- `window.vowOS.service`
- `window.omi_platform`

Per ciascun oggetto vengono enumerati tutti i nomi di proprietà proprie a ogni livello della prototype chain (fino a 10 livelli). Per ogni proprietà vengono salvati:
- nome;
- depth del proprietario;
- descriptor flags;
- tipo del data descriptor;
- valore solo se scalare, oppure tag/shape minimale per array/object;
- source se il valore è una funzione;
- source di getter/setter se presenti.

Il probe non legge i valori degli accessor e non invoca funzioni, getter, setter, init o metodi scoperti. Limite di sicurezza: massimo 250 proprietà per livello; ogni eventuale troncamento viene marcato esplicitamente nel report.

Obiettivo del prossimo test TV: eseguire soltanto **Trace Permission Sources** e poi **Export Report**. Analizzare soprattutto:
- `permissionSourceTrace.runtimeObjectInventory.objects.vowOSContext`
- `permissionSourceTrace.runtimeObjectInventory.objects.vowOSService`
- `permissionSourceTrace.runtimeObjectInventory.objects.omiPlatform`

Cercare metodi non ovvi come initialize/bind/register/setParam/platform/message/context/config/access/bridge o altre funzioni che possano spiegare come il browser/runtime assegna l'identità dell'app prima di `getIdentifier()`.


---

## IMPLEMENTAZIONE — Global Phoenix Wrapper Source Trace — 2026-09-26

Il Complete Runtime Bridge Inventory reale ha mostrato che:
- `vowOSContext` espone solo `init`, `getAppIdentifier`, `getAppId`;
- `omi_platform` espone solo `addPlatformEventListener` e `sendPlatformMessage`;
- `vowOS.service` include un secondo trasporto oltre a `syncExecute`: `execute(module,obj_params)` via WebSocket `wss://localhost:9888`;
- i comandi WebSocket includono `identifier: this.getIdentifier()`;
- la gestione delle risposte conserva le sessioni con `callbacks.method == 'register'`.

Per localizzare eventuali wrapper esistenti che usano questo meccanismo senza eseguire alcun servizio, il Permission Source Trace ora salva:

`permissionSourceTrace.globalPhoenixWrappers`

Il probe:
- enumera le proprietà proprie di `window` tramite descriptor;
- considera soltanto data descriptor il cui valore è già una function, senza leggere accessor;
- esegue anche una scansione bounded di un livello dentro namespace globali object-valued già presenti, sempre tramite descriptor;
- non invoca funzioni/getter/setter;
- cerca nel source delle funzioni i pattern:
  - `vowOS.service.execute(`
  - `phoenix://service/`
  - `method: "register"` / `method: 'register'`
  - assegnazioni `.method = "register"`;
- estrae eventuali path `phoenix://service/...`, source e brevi excerpt contestuali;
- deduplica le function reference e i Phoenix paths.

Limiti:
- massimo 1200 proprietà globali;
- namespace one-level solo se <=200 proprietà;
- massimo 100 function match salvati;
- nessuna chiamata Phoenix/register viene eseguita.

Obiettivo del prossimo test TV: eseguire solo **Trace Permission Sources** e **Export Report**. Analizzare:
- `permissionSourceTrace.globalPhoenixWrappers.matches`
- `permissionSourceTrace.globalPhoenixWrappers.uniquePhoenixPaths`
- `scannedFunctionCount`

Se emergono wrapper concreti, il prossimo probe dovrà seguire soltanto quei nomi/path reali. Se non emerge nulla, la pista JavaScript dei wrapper Phoenix è sostanzialmente esaurita.


---

## IMPLEMENTAZIONE — Global Native Identity Usage Trace — 2026-09-26

Il Global Phoenix Wrapper Source Trace reale ha trovato 4 wrapper concreti su 1192 funzioni analizzate:
- `TvInfo_setParam` -> `phoenix://service/tvinfo`, `callAPI/setbiz`
- `TvInfo_setParamObserver` -> `phoenix://service/tvinfo`, `method:'register'`
- `TvInfo_clearParamObserver` -> `phoenix://service/tvinfo`, `method:'unregister'`
- `TvInfo_writeTvRunLog` -> `phoenix://service/hiutils`, `callAPI/writeTvRunLog`

Il `register` emerso è quindi un observer/event subscription di `tvinfo`, non un client/app identity registration. I soli Phoenix paths scoperti sono `phoenix://service/tvinfo` e `phoenix://service/hiutils`.

Per verificare l'ultima pista JavaScript rimasta — chi usa davvero l'identità nativa — il Permission Source Trace ora salva:

`permissionSourceTrace.globalIdentityUsage`

Il probe usa la stessa copertura bounded del Phoenix trace:
- proprietà proprie di `window` via descriptor;
- one-level scan dei namespace object-valued già presenti;
- massimo 1200 global properties;
- namespace solo se <=200 proprietà;
- deduplica per function reference;
- massimo 150 match salvati.

Pattern cercati nel source delle funzioni:
- `vowOSContext.init(`
- `vowOSContext.getAppIdentifier(`
- `vowOSContext.getAppId(`
- `navigator.appIdentifier`
- `getAppIdentifier(`
- `getAppId(`

Per ogni match salva:
- path globale della funzione;
- ownerDepth;
- functionName/arity;
- source completo;
- matchedPatterns;
- excerpt contestuali.

Il report include anche `patternCounts` per sapere rapidamente quante funzioni visibili contengono ciascun riferimento.

Il probe non invoca alcuna funzione/getter/setter e soprattutto non chiama `vowOSContext.init()`.

Obiettivo del prossimo test TV: eseguire solo **Trace Permission Sources** e **Export Report**, poi analizzare:
- `permissionSourceTrace.globalIdentityUsage.matches`
- `permissionSourceTrace.globalIdentityUsage.patternCounts`

Interpretazione attesa:
- se esistono wrapper che chiamano `vowOSContext.init()`, seguire solo quei wrapper concreti;
- se non esiste alcun riferimento a `init()` e gli unici match sono `vowOS.service.getIdentifier()` / getter nativi, la pista JavaScript per l'inizializzazione dell'identity è sostanzialmente chiusa e l'assegnazione dell'app identifier va considerata runtime/browser-native.


---

## IMPLEMENTAZIONE — AUTOMATIC GITHUB REPORT SYNC — 2026-09-26

Sidee ora supporta la sincronizzazione automatica dei report diagnostici verso GitHub senza esporre credenziali alla TV.

Architettura:
- il browser TV continua a inviare il report solo al server Python locale tramite `POST /api/reports/session`;
- il report locale `reports/sidee-session-....json` viene scritto per primo e rimane sempre la copia autorevole;
- il POST include anche il `reason` dell'autosave;
- il backend accoda l'ultima versione del report a un worker Git separato;
- autosave ravvicinati vengono coalesciti con un debounce configurabile;
- il worker usa esclusivamente il checkout Git locale e le credenziali Git già configurate sul PC;
- nessun token/API key GitHub viene inviato o salvato nel browser TV, in `web/app.js` o in `config.json`.

Branch remoto dedicato:
- default: `sidee-reports`;
- `reports/latest.json` = ultima versione sincronizzata;
- `reports/sessions/sidee-session-....json` = storico per sessione;
- il branch viene creato automaticamente al primo push riuscito se non esiste.

Il sync usa un temporary detached worktree, quindi:
- non cambia branch nel checkout principale;
- non aggiunge/stagea modifiche locali dell'utente;
- non committa file di lavoro non correlati;
- non inquina `main` con i report runtime.

Fallback:
- se Git manca, il checkout non è un repository, l'auth push non è disponibile o il remote fallisce, l'analisi resta valida;
- il JSON locale non viene perso;
- la UI mostra `Saved locally · GitHub sync error: ...`;
- `GET /api/reports/sync` espone lo stato `IDLE / QUEUED / SYNCING / SYNCED / ERROR / DISABLED`.

Configurazione default aggiunta a `config.json`:
- enabled: true
- remote: origin
- branch: sidee-reports
- base_branch: main
- latest_path: reports/latest.json
- history_dir: reports/sessions
- debounce_seconds: 2

Workflow futuro per analizzare un test:
1. eseguire il probe/test sulla Hisense;
2. attendere che la UI mostri `GitHub synced to sidee-reports`;
3. in una nuova chat basta chiedere di analizzare l'ultimo report Sidee;
4. leggere direttamente `reports/latest.json` dal branch `sidee-reports`;
5. non chiedere all'utente di allegare il JSON se il sync risulta disponibile.


---

## IMPLEMENTAZIONE — Client Build ID + Cache Busting — 2026-09-26

Problema osservato:
- un report TV successivo all'aggiunta del Global Native Identity Usage Trace non conteneva affatto `permissionSourceTrace.globalIdentityUsage`;
- il repo `main` conteneva già il probe, quindi la TV aveva eseguito una versione precedente/cachata di `web/app.js`;
- il server già inviava `Cache-Control: no-cache, no-store, must-revalidate`, ma il browser VIDAA non è sufficientemente affidabile da usare solo gli header come garanzia.

Soluzione implementata:

### 1. Build ID content-derived
`sidee.py` calcola `client_build_id()` come SHA-256 dei byte correnti di `web/app.js`, abbreviato a 12 caratteri e prefissato con `app-`.

Quindi il build ID cambia automaticamente ogni volta che cambia davvero `app.js`, senza dover mantenere una versione manuale.

### 2. Cache busting esplicito
`web/index.html` usa:
`/app.js?v=__SIDEE_BUILD_ID__`

Quando il server serve `index.html`, sostituisce `__SIDEE_BUILD_ID__` con il build ID reale calcolato dal contenuto di `app.js`.

Gli asset statici ora ricevono anche:
- `Cache-Control: no-cache, no-store, must-revalidate, max-age=0`
- `Pragma: no-cache`
- `Expires: 0`
- `X-Sidee-Build: <build id>`

L'HTML include anche meta no-cache/no-store come ulteriore fallback per browser TV.

### 3. clientBuildId nel report
`web/app.js` ricava `CLIENT_BUILD_ID` dal parametro `v` del proprio `document.currentScript.src`.

Ogni nuovo report contiene:
- `clientBuildId`
- `serverBuildId`
- `buildMatch`

Prima di ogni salvataggio il client riafferma il proprio `clientBuildId`.

### 4. Verifica client/server
`/api/status` espone il build ID server corrente come `clientBuildId`.

Durante `load()`, Sidee confronta il build ID del JS effettivamente in esecuzione con quello servito dal server.

Anche `POST /api/reports/session` effettua una verifica server-side:
- se il client non invia `clientBuildId`, salva `clientBuildId: "MISSING"`;
- salva sempre `serverBuildId`;
- salva sempre `buildMatch`;
- restituisce questi tre valori nella response.

Questo rende riconoscibile anche un vecchio client che non possiede ancora la logica di build checking.

Se una build nuova rileva mismatch durante il salvataggio, la UI mostra esplicitamente:
`STALE CLIENT · <client> ≠ <server> · reload Sidee before testing.`

### Obiettivo operativo
Dal prossimo JSON, prima di interpretare qualsiasi diagnostica, controllare:
- `clientBuildId`
- `serverBuildId`
- `buildMatch`

Procedere con l'analisi del probe solo se `buildMatch === true`.

Il Global Native Identity Usage Trace resta presente in `web/app.js`; una build aggiornata deve quindi produrre anche:
`permissionSourceTrace.globalIdentityUsage`.


---

## IMPLEMENTAZIONE — SESSION-ARMED REMOTE READ-ONLY DIAGNOSTICS — 2026-09-26

È stato aggiunto un canale remoto volutamente ristretto per poter avviare da una chat il prossimo probe quando la pagina Sidee è già aperta sulla TV.

Vincolo di consenso locale:
- ad ogni load la pagina parte DISARMED;
- l'utente deve premere `Enable remote diagnostics for this page`;
- l'abilitazione esiste solo in memoria e non viene persistita;
- chiusura/reload della pagina la disattiva.

Il comando remoto NON contiene un nome funzione arbitrario. Può richiedere soltanto il workflow fisso read-only:
1. baseline;
2. Permission Source Trace;
3. Installed App Metadata;
4. verification;
5. report export/sync.

Il canale non espone install/uninstall, setter Role/Customer, fileWrite, reset, JavaScript arbitrario o chiamate HiUtils inventate.

Trasporto:
- branch: `sidee-control`;
- request file: `control/request.json`;
- Sidee PC fa polling Git;
- TV legge soltanto `GET /api/remote-diagnostic/request` sul server locale;
- ACK locale: `POST /api/remote-diagnostic/ack`;
- risultato: normale sync in `sidee-reports/reports/latest.json`.

Ogni richiesta reale richiede:
- `requestId` formato `sidee-request-YYYYMMDD-HHMMSS-xxxx`;
- `runSafeDiagnostic: true`;
- `expiresAt` futuro.

Il report salva `remoteDiagnostic.lastRequestId`, timestamps, workflow e status. Prima di analizzare un risultato remoto, verificare sempre che `lastRequestId` corrisponda alla richiesta inviata.


---

## IMPLEMENTAZIONE — Identity Override Lab — 2026-09-26

Questa fase parte dall'evidenza già consolidata: nel contesto Sidee l'identifier nativo è vuoto e la normale pipeline `installApplication` viene respinta dal permission/AppConfig gate. Non sono state rifatte ricerche VIDAA generiche.

È stato aggiunto un nuovo step separato: **Run Identity Override Lab**.

### Candidate identifier reali

Il lab non genera stringhe casuali e non fa brute force. Raccoglie soltanto valori concreti già esposti dalla TV/runtime:

- identity fields correnti (`serviceIdentifier`, `appIdentifier`, `appId`, `navigator.appIdentifier`) quando realmente non vuoti;
- ID/appId/unifiedAppName presenti nella risposta read-only già nota di `websdk/Appinfo.json`;
- ID/appId/unifiedAppName restituiti da `Hisense_getInstalledApps`;
- data-property runtime con nomi fortemente identity-like (`appIdentifier`, `identifier`, `appId`, `clientId`, ecc.), senza invocare accessor.

Token/secret/password/cookie/auth-like values, URL e stringhe eccessivamente lunghe non vengono usati come candidate.

Le candidate vengono deduplicate, ordinate per provenance e nel report ne vengono elencate al massimo 40. Solo le prime 8 vengono realmente provate, evitando test massivi.

### Baseline + override read-only

Il lab usa una sola API innocua già verificata:

`HiUtils_createRequest('fileRead', {path:'websdk/Appinfo.json', mode:6})`

Prima acquisisce la baseline con l'identifier originale.

Per ogni candidate:

1. salva il descriptor/stato originale di `vowOS.service.getIdentifier`;
2. applica un override temporaneo;
3. ripete esattamente la stessa `fileRead`;
4. salva request, `ret/code/msg`, risposta e differenza dalla baseline;
5. ripristina sempre l'implementazione originale in `finally`;
6. registra se il restore è riuscito.

Se una risposta è identica alla baseline, il test salva un riferimento alla risposta baseline invece di duplicare il grande payload Appinfo.

### Conclusioni automatiche

Il lab può produrre:

- `NO_REAL_IDENTIFIER_AVAILABLE`;
- `IDENTIFIER_AFFECTS_BACKEND`;
- `INCONCLUSIVE`.

Il semplice fatto che una candidate non cambi `fileRead` NON viene trasformato in `IDENTIFIER_STRING_NOT_SUFFICIENT`, perché `fileRead` non è noto per usare lo stesso permission gate di `installApplication`.

`IDENTIFIER_STRING_NOT_SUFFICIENT` viene usato soltanto dopo il nuovo **Candidate Permission Gate Test** esplicito se quella candidate continua a ricevere il noto errore AppConfig/permission 503.

### Permission gate esplicito

Sotto Advanced è presente **Candidate Permission Gate Test**.

È volutamente separato dal lab e dal workflow remoto perché invia una reale richiesta install con l'identifier temporaneo. Se il firmware la accetta, il target potrebbe realmente essere registrato/installato. Il callback esterno `0` continua a non essere considerato successo; la verification resta l'unica prova di installazione.

### Report

Il report di sessione contiene:

- `identityOverrideLab`: timestamp/build IDs, originalIdentifier, candidateIdentifiers con provenance, baselineProbe, tests, responseDiff, restore state, conclusionHint/conclusionNote;
- `candidatePermissionTest` per il test install esplicito separato.

### Remote diagnostics

Il workflow remoto session-armed resta read-only ma ora include anche Identity Override Lab:

`baseline -> identity-override-lab -> permission-source-trace -> installed-metadata -> verification -> export`

Non sono stati aggiunti install/uninstall, setter, fileWrite, reset o comandi arbitrari al canale remoto.


---

## NUOVA PRIORITÀ — Direct AppInfo fileWrite Lab — 2026-09-26

### Ricerca mirata nuova

Fonte 1 — Pikabu, post `Jellyfin на Vidaa 9`:
- URL: `https://pikabu.ru/story/jellyfin_na_vidaa_9_13617347`;
- data mostrata dalla fonte: 2026-01-21;
- affidabilità: esperienza riportata da terzi, non documentazione Hisense;
- l’autore dichiara di aver testato il metodo su VIDAA OS 9;
- il codice legge `websdk/Appinfo.json`, modifica `AppInfo` e scrive con `HiUtils_createRequest('fileWrite', { path:'websdk/Appinfo.json', mode:6, writedata: JSON.stringify(apps) })`;
- dopo il write la guida richiede riavvio TV e riferisce che l’app compare in fondo alla lista;
- la fonte prova Jellyfin sul dispositivo dell’autore e NON dimostra compatibilità con `50E70LEVS_0003 / V0000.09.60A.Q0707`.

Fonte 2 — `weinzii/vidaa-edge`, commit `94c3134911cbd4b813eea1f88c56819c0981518b`:
- file: `src/app/services/app-management.service.ts`;
- affidabilità: codice sorgente pubblico direttamente rilevante, non API ufficiale Hisense;
- `installAppNew()` usa la stessa chiamata `fileWrite` con lo stesso path, mode e campo `writedata`;
- la entry new-method contiene `Id`, `AppName`, `Title`, `URL`, `StartCommand`, quattro campi icona, `Type:'Browser'`, `InstallTime`, `RunTimes:0`, `StoreType:'custom'`, `PreInstall:false`.

Conseguenza pratica:
- non serve inventare la firma `fileWrite`;
- la priorità passa temporaneamente dall’Identity Override Lab alla verifica controllata della capability `fileWrite`;
- il primo test NON aggiunge applicazioni e riscrive la stringa `msg` originale senza re-serializzarla.

### Implementazione `directAppInfoWriteLab`

È stata aggiunta una nuova sezione principale **Direct AppInfo Write Lab** con:
- `Test AppInfo Direct Write`;
- `Add Nuvio to AppInfo` separato e inizialmente disabilitato;
- `Restore AppInfo Backup` separato.

L’Identity Override Lab resta nel codice ma la card principale è nascosta/PAUSED e non viene più eseguita dal workflow remoto read-only.

### No-op write capability test

Il test:
1. richiede `buildMatch === true`;
2. esegue `fileRead` su `websdk/Appinfo.json`;
3. conserva raw string completa + parsed JSON + fingerprint + lunghezza + AppInfo count;
4. valida obbligatoriamente un oggetto JSON con array `AppInfo`;
5. invia la raw string completa al server Sidee per un backup immutabile;
6. il server calcola SHA-256, confronta l’eventuale SHA-256 client e salva sotto `backups/appinfo/<sessionId>/`;
7. solo dopo backup riuscito chiama `HiUtils_createRequest('fileWrite', {path:'websdk/Appinfo.json', mode:6, writedata:<raw originale>})`;
8. esegue subito un nuovo fileRead;
9. confronta hash, lunghezza, numero entry e struttura JSON.

Classificazioni:
- `WRITE_ALLOWED_AND_IDENTICAL`;
- `WRITE_DENIED`;
- `WRITE_CHANGED_CONTENT`;
- `READBACK_FAILED`;
- `INCONCLUSIVE`.

Se write/readback cambia contenuto, Sidee non prosegue automaticamente con altre scritture.

### Backup server-side

Nuovo endpoint:
- `POST /api/appinfo/backup` crea un backup non sovrascrivibile;
- `GET /api/appinfo/backup?sessionId=...&backupId=...` legge soltanto un backup Sidee validato.

Protezione:
- sessionId usa la regex sessione già esistente;
- backupId ha formato stretto `appinfo-backup-YYYYMMDD-HHMMSS-xxxxxxxx`;
- path derivati server-side;
- JSON deve contenere `AppInfo` array;
- limite 4 MiB;
- write con modalità esclusiva `x`;
- SHA-256 server-side.

`backups/` è gitignored.

### Candidate Nuvio conservativa

La candidate direct entry usa il minimo shape **noto funzionante nelle due fonti pubbliche**, non un minimo teoricamente provato:
- Id / AppName / Title;
- URL / StartCommand;
- IconURL / Icon_96 / Image / Thumb;
- Type `Browser`;
- InstallTime;
- RunTimes `0`;
- StoreType `custom`;
- PreInstall `false`.

Non vengono inventati:
- openMode;
- venderId;
- packaged;
- configUrl/configUrlDownload/mediaId.

Motivo: la guida Pikabu e il metodo nuovo di vidaa-edge non li richiedono; inoltre i record reali già osservati sulla TV mostrano valori differenti (Smartone openMode 98, Stremio 99, Duplecast 98; venderId 9999), quindi copiarli senza evidenza sarebbe speculativo.

### Add Nuvio

`Add Nuvio to AppInfo` si abilita solo dopo `WRITE_ALLOWED_AND_IDENTICAL`.

Prima di scrivere:
- rilettura fresca;
- nuovo backup immutabile;
- controllo duplicati per Id, URL, AppName/Title;
- nessuna scrittura se esiste già un match.

Dopo la scrittura:
- readback;
- verifica `APPINFO_ENTRY_PRESENT`;
- verifica che tutte le entry precedenti siano strutturalmente preservate;
- `LAUNCHER_APP_VISIBLE` resta `UNKNOWN_REBOOT_REQUIRED`;
- `APP_LAUNCHES` resta `NOT_TESTED`.

Il ritorno `fileWrite` non viene confuso con la presenza nel registry o la visibilità launcher.

### Restore

Restore usa esclusivamente il backup originale creato da Sidee nella stessa sessione.
Prima del restore:
- legge e valida il registry corrente;
- crea un ulteriore backup pre-restore;
- ricarica il backup originale dal server;
- verifica sessionId / backupId / SHA-256;
- esegue fileWrite;
- fa readback;
- dichiara `RESTORED_IDENTICAL` solo con hash/struttura confermati.

Nessun rollback automatico.

### Remote diagnostic

Lo stesso canale `sidee-control` è stato esteso, non duplicato.

Request supportate:
- `runSafeDiagnostic:true` -> workflow read-only esistente, ora senza Identity Override Lab;
- `runDirectAppInfoWriteNoop:true` -> solo no-op AppInfo write con backup/readback.

Le due modalità sono mutuamente esclusive.
Il vecchio server ignora `runDirectAppInfoWriteNoop`, quindi è possibile pubblicare una richiesta che diventerà eseguibile soltanto dopo `git pull` + restart della nuova build.

Il remote workflow NON può:
- aggiungere Nuvio;
- fare restore;
- install/uninstall;
- invocare setter;
- eseguire JavaScript arbitrario.


### HARDENING — Direct AppInfo write build binding

Prima del test reale sono stati aggiunti due gate:
- ogni no-op/add/restore rilegge `/api/status` immediatamente prima del flusso di scrittura e rifiuta un client stale;
- il backup server riceve `clientBuildId` e rifiuta la creazione se non coincide con il build corrente;
- per le richieste create dalla chat si usa `runDirectAppInfoWriteNoopV2:true` + `requiresBuildId`;
- il vecchio server non riconosce il flag V2, quindi non può consumare accidentalmente la nuova richiesta;
- il server nuovo consegna una request V2 AppInfo soltanto a una pagina che dichiara lo stesso `clientBuildId`.


---

## TEST REALE — Direct AppInfo fileWrite RESPINTO — 2026-09-26

Report valido:
- sessionId `sidee-20260926-104537-d029`;
- clientBuildId `app-e29e348ed744`;
- serverBuildId `app-e29e348ed744`;
- `buildMatch: true`;
- remote request `sidee-request-20260926-120654-a36d`;
- workflow `direct-appinfo-noop` completato.

Backup pre-write creato correttamente:
- backupId `appinfo-backup-20260926-121218-af9c001f`;
- SHA-256 `d4869d266a085485c4bcf52b66202cf67bad90ebdbb8a6c36be9090c81405878`;
- 7173 bytes;
- 3 entry AppInfo.

Risposta reale di `HiUtils_createRequest('fileWrite', ...)`:
- `ret:false`;
- `code:503`;
- `msg:'client request permission check error, please check appconfig'`;
- sdkVersion `1.5.0`.

Readback immediato:
- JSON valido;
- 3 entry AppInfo;
- SHA-256 identico al backup/originale;
- `identicalBeforeAfter:true`.

Classificazione finale:

`WRITE_DENIED`

Conclusione: sulla Hisense `50E70LEVS_0003`, firmware `V0000.09.60A.Q0707`, il metodo Jellyfin/Pikabu NON bypassa il permission/AppConfig gate nel contesto Sidee corrente. Il gate non è specifico di `installApplication`: anche la `fileWrite` diretta di `websdk/Appinfo.json` viene respinta con lo stesso code 503.

Azioni deliberate dopo il risultato:
- Nuvio NON è stato aggiunto;
- nessun restore necessario perché il readback è identico;
- nessuna ulteriore scrittura automatica;
- la request V2 ridondante è stata annullata su `sidee-control`;
- Identity Override Lab torna a essere la pista prioritaria e viene riattivato nel workflow remoto read-only.

Non ripetere il Direct AppInfo no-op write su questo firmware salvo cambiamento firmware/runtime o nuova evidenza concreta.


### HARDENING — build-bound read-only remote workflow

Per evitare che il server attualmente vecchio consumi la prossima request prima del pull/restart, è supportato anche `runSafeDiagnosticV2:true` con `requiresBuildId`.
Il vecchio server non riconosce il flag V2. Il server nuovo accetta e consegna la request soltanto quando server e pagina TV espongono esattamente il build richiesto.
Questo permette di mettere in coda in anticipo il prossimo workflow read-only con Identity Override Lab senza falso completamento da cache/build precedenti.


---

## IMPLEMENTAZIONE — RAW-IP HTTP ORIGIN A/B TEST — 2026-09-26

Motivazione:
- il no-op `fileWrite` su `https://vidaahub.com` è stato respinto su questa TV con lo stesso errore noto:
  - `ret:false`
  - `code:503`
  - `client request permission check error, please check appconfig`;
- una guida Pikabu su VIDAA 9 riferisce invece un flusso aperto direttamente da un URL LAN HTTP tipo `http://192.168.x.x:8080`, quindi senza dipendere dal dominio spoofato;
- `weinzii/vidaa-edge` usa normalmente `https://vidaahub.com` su 443, ma issue #30 documenta lo stesso errore AppConfig su firmware 09.60 anche con configurazioni alternative.

Confronto setup effettuato:
- Sidee e vidaa-edge coincidono sui punti principali del trusted-host setup:
  - hostname `vidaahub.com`;
  - HTTPS;
  - porta 443;
  - bind `0.0.0.0`;
  - certificato self-signed per vidaahub.com;
- il certificato incluso in vidaa-edge non costituisce una differenza favorevole: è un self-signed statico e non dimostra alcun legame con l'autorizzazione AppConfig;
- quindi resta utile solo un confronto A/B diretto dell'origin.

Implementazione:
- nuovo config `existing `http_port: 8080``;
- Sidee avvia una seconda UI HTTP su `http://<PC-IP>:8080`, oltre al dashboard 8080 e a HTTPS 443;
- `/api/status` espone anche:
  - `requestScheme`;
  - `requestPort`;
- ogni report registra:
  - `accessContext.href`;
  - `accessContext.origin`;
  - `accessContext.protocol`;
  - `accessContext.hostname`;
  - `accessContext.port`;
  - `accessContext.host`;
  - `accessContext.secureContext`;
  - `serverAccess` con scheme/port/Host realmente visti dal server;
- il Direct AppInfo Write Lab incorpora lo stesso page/server context nel risultato;
- la UI mostra sempre `Access origin`.

Protocollo test:
A. baseline già nota:
`https://vidaahub.com` -> no-op fileWrite -> 503 AppConfig.

B. dopo pull + restart:
1. aprire sulla TV `http://<PC-IP>:8080`;
2. non cambiare il DNS;
3. verificare se le API VIDAA sono presenti;
4. catturare baseline;
5. eseguire solo `Test AppInfo Direct Write`;
6. non aggiungere Nuvio;
7. confrontare report e risposta con il caso A.

Interpretazione:
- se le API non vengono iniettate su raw IP, il trusted hostname resta necessario solo per l'esposizione API;
- se fileRead funziona ma fileWrite restituisce ancora 503, DNS/origin è sostanzialmente escluso come causa del gate;
- se il no-op write diventa `WRITE_ALLOWED_AND_IDENTICAL`, allora l'origin/launch path è materialmente rilevante e va investigato prima dell'identity spoofing.


---

## RISULTATO — RAW-IP HTTP A/B + NUOVA PISTA APP-CONTEXT — 2026-09-26

### Raw-IP A/B concluso

Sessione raw-IP:
- origin: `http://192.168.1.5:8080`;
- protocollo: HTTP;
- DNS TV: automatico;
- buildMatch: true;
- `fileRead websdk/Appinfo.json`: `ret:true`, `code:0`, 3 entry;
- no-op `fileWrite`: `ret:false`, `code:503`, `client request permission check error, please check appconfig`;
- readback identico, nessuna modifica al registry.

Conclusione:
- DNS spoof e hostname `vidaahub.com` NON sono la causa del 503;
- la capability `fileRead` è esposta anche da raw IP su questo firmware;
- il write gate resta AppConfig/permission e dipende da qualcosa di diverso dall'origin DNS.

### Evidenza pubblica coerente

Issue `weinzii/vidaa-edge#30`:
- firmware `V0000.09.60F.Q0528`: stesso errore AppConfig su new method;
- commenti successivi riportano lo stesso errore anche su:
  - `V0000.09.60C.Q0516`;
  - `V0000.09.60A.Q0602`;
- un commento dell'autore di vidaa-edge sostiene che firmware >= v9 possa esporre le funzioni senza DNS rewrite, ma altri utenti 09.60 confermano che il write resta bloccato con o senza DNS.

La TV Sidee usa `V0000.09.60A.Q0707`, coerente con questa famiglia di comportamento.

### HiZ-Store / simonbuehler

Nel thread `PhasedGapple/HiZ-Store#1`, simonbuehler pubblicò nel 2025 il direct AppInfo `fileWrite` e dichiarò anche di aver ottenuto developer mode / controllo completo del servizio su una sua TV. Il direct-write risultava funzionante su almeno firmware `V0000.09.09P.P0930`, ma non dimostra compatibilità con le build 09.60.

Esiste inoltre `PhasedGapple/FuVIDAA-API`, che sperimenta l'API della app store moderna su `category-ui.vidaahub.com`; è una pista futura perché il vero app-store context potrebbe possedere un AppConfig privilegiato, ma il PoC pubblico non dimostra ancora una procedura completa e stabile sulle build 09.60.

### Nuova ipotesi ad alta priorità: installed-app context trampoline

Il runtime già osservato mostra che `vowOS.service.getIdentifier()` prende l'identità da `vowOSContext.getAppIdentifier()`. Il browser manuale restituisce identità vuota.

Ipotesi:
- un'app realmente lanciata dal VIDAA launcher può ricevere una identity nativa non vuota;
- se carichiamo Sidee dentro quel container tramite DNS temporaneo, il service request potrebbe essere autorizzato diversamente.

Scelti due target già installati con URL HTTP, così non serve MITM TLS:
- Smartone IPTV:
  - Id `1470`;
  - URL `http://vidaa.smartone-iptv.com`;
- Duplecast:
  - Id `1876`;
  - URL `http://vidaa.duplecast.com/`.

Implementazione:
- entrambi i domini aggiunti a `spoof_domains`;
- nuovo listener HTTP Sidee su porta 80;
- config `app_context_probe` documenta app/host;
- report registra `accessMode`;
- modalità riconosciute:
  - `SMARTONE_APP_CONTEXT`;
  - `DUPLECAST_APP_CONTEXT`;
  - `VIDAAHUB_BROWSER_CONTEXT`;
  - `RAW_IP_BROWSER_CONTEXT`;
  - `OTHER_CONTEXT`;
- UI mostra `Access mode`.

Protocollo:
1. git pull + restart Sidee;
2. TV DNS -> IP PC;
3. non aprire browser;
4. lancia Smartone IPTV dal launcher VIDAA;
5. se carica Sidee, Capture Baseline;
6. controllare identity reale;
7. eseguire solo no-op Direct AppInfo Write;
8. se Smartone non carica, provare Duplecast;
9. Add Nuvio solo con `WRITE_ALLOWED_AND_IDENTICAL`;
10. ripristinare DNS automatico a fine test.

Interpretazione:
- identity non vuota + write consentito => soluzione pratica: usare installed-app container come trampoline per registrare Nuvio;
- identity non vuota + 503 => AppConfig permission è per-app e l'app normale non ha write privilege; prossima pista = official App Store context / category-ui;
- identity vuota => launcher non assegna identity utile a quel tipo di app; passare al contesto store ufficiale.


---

## IMPLEMENTAZIONE — Identifier Write-Gate Lab — 2026-09-26

Motivazione: il confronto raw-IP vs `vidaahub.com` ha chiuso la variabile origin/DNS. Entrambi raggiungono `hiutils`; `fileRead` passa con identifier vuoto, mentre `fileWrite` riceve lo stesso AppConfig 503. Di conseguenza il vecchio Identity Override Lab su `fileRead` non è più discriminante.

Nuovo test esplicito:
- fresh build check;
- read completo di `websdk/Appinfo.json`;
- backup immutabile server-side prima di qualsiasi write;
- baseline no-op `fileWrite` con identifier corrente;
- readback identico obbligatorio;
- raccolta esclusiva di candidate concrete da runtime/AppInfo/installed apps;
- massimo 6 candidate;
- per ogni candidate: override temporaneo di `vowOS.service.getIdentifier`, stesso identico raw `fileWrite`, readback, restore in `finally`;
- stop immediato se cambia il gate o cambia il registry;
- Nuvio non viene mai aggiunto.

Conclusioni:
- `IDENTIFIER_AFFECTS_WRITE_GATE`: una candidate cambia ret/code/msg/error del vero `fileWrite` gate;
- `IDENTIFIER_STRING_NOT_SUFFICIENT`: tutte le candidate concrete testate ricevono lo stesso AppConfig rejection della baseline;
- `NO_REAL_IDENTIFIER_AVAILABLE`;
- `BASELINE_WRITE_ALLOWED`;
- `REGISTRY_CHANGED_ABORTED`;
- `INCONCLUSIVE`.

Remote:
- nuovo flag esclusivo `runIdentityWriteGateLabV1:true`;
- obbligatorio `requiresBuildId` uguale al build server;
- workflow remoto `baseline -> identity-write-gate-lab -> export`;
- nessun add Nuvio, restore, install/uninstall, setter o JavaScript arbitrario.


---

## TEST REALE — Identifier Write-Gate Lab — 2026-09-26

Sessione valida:
- sessionId `sidee-20260926-150815-b6a2`;
- accessMode `RAW_IP_BROWSER_CONTEXT`;
- origin `http://192.168.1.5:8080`;
- clientBuildId/serverBuildId `app-7c6c95bcb6e0`;
- `buildMatch:true`.

Baseline:
- originalIdentifier `""`;
- `fileWrite websdk/Appinfo.json` no-op -> `ret:false`, `code:503`, `client request permission check error, please check appconfig`;
- readback valido e identico;
- 3 AppInfo entry;
- backup pre-test `appinfo-backup-20260926-130830-ec656ca0`;
- backup SHA-256 `d4869d266a085485c4bcf52b66202cf67bad90ebdbb8a6c36be9090c81405878`.

Candidate concrete testate contro il vero write gate:
- `1470` — Smartone IPTV;
- `1876` — Duplecast;
- `2568` — Stremio Lite.

Per tutte e tre:
- override `vowOS.service.getIdentifier` applicato via assignment;
- write response identica alla baseline: `ret:false`, `code:503`, stesso msg AppConfig;
- `backendChanged:false`;
- readback identico;
- registry invariato;
- override ripristinato correttamente a identifier vuoto.

Conclusione:

`IDENTIFIER_STRING_NOT_SUFFICIENT`

Interpretazione precisa: per le tre candidate concrete derivate dagli AppInfo ID installati, cambiare soltanto la stringa dell'header `identifier` non è sufficiente a superare il permission/AppConfig gate. Questo non prova che l'identifier non conti mai; prova che gli AppInfo ID `1470/1876/2568` non sono da soli una identity autorizzata equivalente a un vero launch context.

Conseguenza:
- chiudere la pista 'spoof stringa con app ID';
- non ripetere questi tre identifier sullo stesso firmware;
- prossima pista prioritaria: installed-app context trampoline, cioè ottenere una vera identity nativa lanciando Sidee dentro Smartone/Duplecast dal launcher;
- se il launch context restituisce identity non vuota ma write resta 503, passare al contesto App Store ufficiale/category-ui.


## UPDATE — 2026-09-26 — Native client context fingerprint

### Result just established by the RAW-IP Identifier Write-Gate report

Report `sidee-session-20260926-150815-b6a2` was executed from `http://192.168.1.5:8080/` (`RAW_IP_BROWSER_CONTEXT`, insecure HTTP). The native `fileRead` of `websdk/Appinfo.json` still succeeded, while the exact no-op `fileWrite` returned `ret:false`, `code:503`, `client request permission check error, please check appconfig`.

The same protected no-op write was then repeated while temporarily overriding only `vowOS.service.getIdentifier()` with three concrete IDs already present in the TV registry:

- `1470` — Smartone IPTV;
- `1876` — Duplecast;
- `2568` — Stremio Lite.

All three produced the same 503 response as the empty-identifier baseline. Every immediate readback remained identical and the registry was restored/unchanged.

Evidence-based conclusion:

`IDENTIFIER_STRING_NOT_SUFFICIENT`

This rules out the hypothesis that the VIDAA 9.60 AppConfig gate can be bypassed merely by changing the JavaScript identifier string. It also adds evidence that DNS/hostname/HTTPS alone are not the gate, because the raw-IP context reproduces the same rejection.

### New bounded probe implemented

Sidee now includes a `Context Identity Fingerprint` designed to answer the remaining question: whether a store-installed launcher container carries native client/AppConfig state that the ordinary browser/raw-IP contexts lack.

When Sidee is opened by the already-installed Smartone or Duplecast launcher entries, the fingerprint runs automatically. It records:

- expected installed-app context (`1470` Smartone or `1876` Duplecast);
- `navigator.appIdentifier`;
- `vowOS.service.getIdentifier()`;
- `vowOSContext.getAppIdentifier()`;
- `vowOSContext.getAppId()`;
- Role ID / Customer ID;
- `Hisense_SupportAppConfig()`;
- bounded own data-property metadata already present on `vowOS.service`, `vowOSContext`, `navigator`, and `window`.

Safety properties:

- no setters;
- no unknown accessors;
- no install/uninstall;
- no file write;
- no guessed HiUtils calls;
- token/secret/auth/cookie/key/signature/certificate/nonce/session-like fields are redacted.

Possible descriptive classifications:

- `INSTALLED_APP_IDENTITY_MATCH`;
- `INSTALLED_APP_IDENTITY_PRESENT`;
- `INSTALLED_APP_METADATA_PRESENT`;
- `INSTALLED_APP_CONTEXT_ANONYMOUS`;
- `BROWSER_IDENTITY_PRESENT`;
- `APPCONFIG_SIGNAL_ONLY`;
- `ANONYMOUS_LIKE`.

The normal safe remote diagnostic workflow also captures this fingerprint.

### Interpretation of the next real-TV test

Launch Smartone IPTV or Duplecast from the VIDAA launcher while DNS points to Sidee. Do not open the normal browser. Sidee should load under the app's own hostname and automatically capture the fingerprint.

Then the separate backup-protected Direct AppInfo no-op write remains the decisive permission check:

- if the installed-app context exposes a non-empty/matching native identity **and** the no-op write changes from 503 to allowed, the client/container identity is materially involved in the permission gate;
- if native identity changes but write remains 503, the gate requires additional AppConfig/ACL state beyond the exposed JS identity fields;
- if the installed-app context still reports anonymous-like identity, the launcher entry/hostname does not by itself create the required privileged client context on this firmware.

Do not treat `Hisense_SupportAppConfig()` by itself as proof of write permission.


### Windows TCP/80 fix — 2026-09-26

The installed-app trampoline uses the apps' real HTTP StartCommand on the default TCP port 80. A Windows-specific launcher bug was found: `start-windows.bat` opened UDP/53, TCP/443 and TCP/8080 in Windows Firewall, but not TCP/80. That can leave Smartone/Duplecast on the VIDAA loading spinner even while the normal Sidee browser UI works correctly.

The Windows launcher now also creates the `Sidee HTTP TCP 80` inbound firewall rule. The TCP/80 listener is also treated as critical: if it cannot bind (for example because another local service already owns port 80), Sidee prints a clear error and stops instead of silently continuing with a broken installed-app test.

For a valid trampoline run the terminal must show:

```
[HTTP] http://0.0.0.0:80 (installed-app context)
```

If the launcher still spins after that, the DNS/HTTP transport tracing in the current build should distinguish “TV never resolved the app hostname” from “DNS reached Sidee but HTTP never arrived” from “the bootstrap page executed”.


## Installed-app AppInfo write-gate test — 2026-09-26

The Duplecast trampoline has now proven a real installed-app native context on the tested TV:

- access mode `DUPLECAST_APP_CONTEXT`;
- `appId = "1876"`;
- `navigator.appIdentifier = {"appid":"1876","md5":"ba9a56ce0a9bfa26e8ed9e10b2cc8f46","permissions":""}`;
- `vowOS.service.getIdentifier() = "UMdO2+D/C/NrEj31J4Ylxw=="`;
- `vowOSContext.getAppIdentifier()` returns the same native identifier;
- `Hisense_SupportAppConfig() = true`;
- `HiUtils_createRequest` is available even though the high-level install/FileRead/FileWrite wrappers are not exposed.

This confirms that a real launcher-created VIDAA app context carries richer native identity than the previously tested JavaScript override of `getIdentifier()`.

The bootstrap page now exposes an explicit **Run backup-protected AppInfo no-op write** action. It never runs automatically. The action:

1. calls `HiUtils_createRequest("fileRead", {path:"websdk/Appinfo.json", mode:6})`;
2. sends the exact raw registry to Sidee's existing immutable backup endpoint;
3. proceeds only after the server confirms the backup;
4. calls `HiUtils_createRequest("fileWrite", ...)` exactly once with the same raw string;
5. immediately reads AppInfo again;
6. posts the write response and raw readback to `/api/app-context-noop-result`;
7. the server reloads the immutable backup and independently compares the readback bytes/hash/count;
8. the same app-context session report is updated and synced to `sidee-reports`.

Possible classifications are `WRITE_ALLOWED_AND_IDENTICAL`, `WRITE_DENIED`, `WRITE_CHANGED_CONTENT`, `READBACK_FAILED`, or `INCONCLUSIVE`.

No Nuvio entry is added by this test. A successful native-context no-op write is still only a capability result; app addition remains a separate later decision.


## Native app-context bridge-source capture — 2026-09-26

Smartone IPTV and Duplecast both produced the same protected-write result from their genuine launcher-created app contexts: native identity present, `navigator.appIdentifier` containing the real app ID plus an MD5 and `permissions:""`, `Hisense_SupportAppConfig() === true`, but exact no-op `HiUtils_createRequest('fileWrite', ...)` still rejected with code 503 and unchanged readback.

This rules out hostname/origin alone, a simple app-ID override, and merely launching inside an installed store app as sufficient explanations.

The installed-app bootstrap now also captures, read-only, bounded function source/descriptors for:
- `HiUtils_createRequest`;
- `vowOS.service.syncExecute`;
- `vowOS.service.getIdentifier`;
- `vowOS.service.executeHttpRequest`;
- `vowOSContext.init`;
- `vowOSContext.getAppIdentifier`;
- `vowOSContext.getAppId`.

It also records bounded property names for `vowOS.service` and `vowOSContext`, excluding names that look like tokens, credentials, cookies, keys, signatures, certificates, nonces or sessions. No unknown accessor is invoked by this source capture.

Goal: determine whether the JavaScript bridge passes only explicit `api + args` or whether native client/AppConfig metadata is attached out-of-band below the visible JavaScript identifier layer.


## Bridge authorization finding — 2026-09-26

A genuine launcher-created Duplecast context exposed the JavaScript bridge sources. The visible request path is now verified:

```text
HiUtils_createRequest(type,msg)
  -> vowOS.service.syncExecute('hiutils', {api:type,args:msg})
  -> vowOS.service.executeHttpRequest(...)
  -> POST https://localhost:9888/service/hiutils
     header: identifier = vowOS.service.getIdentifier()
     body: JSON.stringify({api,args})
```

`vowOS.service.getIdentifier()` delegates to native `vowOSContext.getAppIdentifier()` when the runtime app context exists. No MD5, permissions object, origin metadata or AppInfo record is visibly appended by these JavaScript wrappers.

The real Duplecast and Smartone launcher contexts both had:
- correct real app IDs;
- distinct app MD5 values in `navigator.appIdentifier`;
- non-empty native app/service identifiers;
- `Hisense_SupportAppConfig() === true`;
- `permissions:""`;
- the same code 503 AppConfig rejection for exact no-op `fileWrite`.

Therefore the current evidence points to permission resolution below the visible JavaScript wrapper layer, keyed at least by the native identifier/session context. A valid installed-app identity is not equivalent to write permission.

---

## VERIFICA — Legacy writer unavailable / context-only capture — 2026-09-26

### Stato reale e report

- Prima delle modifiche, `main` e `origin/main` coincidevano su
  `be3991b1488349b514862a1aae6a42655b81ab4f`; working tree pulito.
- Recuperato `origin/sidee-reports` su `0a9b873c948eecf65f72498fd241d9c779f47c47`.
- Fonte: `reports/latest.json`, sessione `sidee-20260926-172629-e5b8`, aggiornata
  `2026-09-26T15:28:00.775Z`; client/server `app-08cafb236b7f`, `buildMatch:true`.
- Il test legacy delle `15:27:20.386Z` gira in `VIDAAHUB_BROWSER_CONTEXT`.
  Prima e dopo: unico owner rilevato `Hisense` (object), `File` assente,
  `loadLibrary` non disponibile; nessuna superficie HiBrowser rilevata.
  `resolutionAttempts` contiene soltanto Hisense, senza caricamento libreria.
- `selectedOwner`, registry, backup, probe e restore sono null;
  `readAttempts` è vuoto. Risultato storico `INCONCLUSIVE`, errore
  `Neither Hisense nor HiBrowser exposed a usable legacy File.read/File.write surface`.
  Non è una scrittura rifiutata: nessun writer è stato raggiunto e nessun file
  è stato letto/scritto da questo test. Non autorizza l'aggiunta Nuvio.
- Il vecchio snapshot non distingue bene assenza/accessor/errori degli host:
  l'assenza della superficie nel report non prova l'assenza di HSPDK nel firmware.

### Ricerca mirata e limiti

- Fonte primaria del codice storico: post oceansize #5237, 2022-03-07,
  https://4pda.to/forum/index.php?showtopic=1004810&st=5220 .
  Il codice disponibile nell'indice della pagina usa direttamente
  `Hisense.File.read('launcher/Appinfo.json',1)` e
  `Hisense.File.write('launcher/Appinfo.json',writedata,1)`.
  Nel listato non c'è bootstrap, script esterno o `loadLibrary` precedente.
  Il post descrive una pagina servita dal PC aperta nel browser TV; non identifica
  una pagina di sistema HSPDK. L'accesso diretto alla pagina ha restituito 403;
  il listato era leggibile nel risultato indicizzato. Esperienza di terzi del
  2022, non prova di compatibilità con VIDAA 9.60.
- Verificato via GitHub il file `src/app/services/app-management.service.ts`
  di https://github.com/weinzii/vidaa-edge e dei fork `marmas1503/vidaa-edge`,
  `WawRepo/vidaa-edge`, `BastyJuice/vidaa-edge`, `simonbuehler/vidaa-edge`.
  Nei primi quattro il file contiene HiUtils `fileWrite` e `Hisense_installApp`,
  senza `HiBrowser`, HSPDK o `File.write`; il file del fork simonbuehler contiene
  soltanto il percorso `Hisense_installApp`. Questo controllo riguarda quei file,
  non dimostra l'assenza di altre superfici in tutti i fork/storia Git.
- Issue https://github.com/weinzii/vidaa-edge/issues/30 e relativi commenti:
  nessun bootstrap HSPDK o secondo writer concreto nei contenuti verificati.
- Le query esatte `libhspdk-jsx.so`, `HiBrowser.loadLibrary` e combinazioni con
  Hisense non hanno fornito nuova evidenza utile. Non attribuire al post 4PDA
  il fallback `libhspdk-jsx.so`: esiste nel codice Sidee ma non nel listato citato.
- Non è stata identificata una pagina/app di sistema che esponga HSPDK sulla
  TV specifica. Nessun nuovo nome API o URL di sistema è stato inventato/provato.

### Implementazione verificata localmente

- Nuovo `web/hspdk-context.js`, condiviso da UI e bootstrap inline, salva
  `legacyHspdkContext`: Hisense/HiBrowser anche se assenti o accessor, proprietà
  e prototype, altri globali reali con File/loadLibrary, riferimenti nel source
  delle funzioni già esistenti e inventario degli script caricati.
- Descriptor-only: il nuovo collector non invoca getter, loader, File.read/write,
  HiUtils o funzioni scoperte. Non recupera/esegue script remoti. Limiti:
  1600 globali, 4000 proprietà di namespace, 100 per namespace, 40 source match,
  30 superfici, 80 script; proprietà sensibili filtrate, troncamenti segnalati.
- Pulsante `Inspect HSPDK Context (read-only)` nel lab legacy. Il test write
  esistente ora classifica `WRITER_UNAVAILABLE` quando non trova il writer e
  conserva anche la nuova cattura. Nessuna nuova API write introdotta.
- Trovato nel codice reale un automatismo non allineato al vecchio README:
  il bootstrap Smartone/Duplecast chiamava `autoRunNoopWriteOnce()` dopo il save.
  Rimosso tutto il flusso no-op dal bootstrap per evitare di ripetere HiUtils 503.
  Ora salva automaticamente il contesto HSPDK insieme all'identità read-only.
- Build ID include app.js, collector, index.html e sidee.py. Il bootstrap invia
  il build incorporato nell'HTML e il server confronta quello ricevuto: non marca
  più indiscriminatamente un bootstrap vecchio come `buildMatch:true`.
- Test locali passati: parsing JavaScript, discovery di File ereditato e host
  alternativi/alias, accessor non invocati, assenza Hisense/HiBrowser gestita,
  source match senza invocazione, esecuzione del bootstrap realmente generato
  con HiUtils/timer proibiti, persistenza del campo nel report, build stale rilevata.
  Nessuna di queste simulazioni dimostra disponibilità del writer sulla TV.

Prossimo dato necessario: dopo restart Sidee, cattura HSPDK nel browser tramite
il nuovo pulsante e nei contesti Smartone/Duplecast tramite il bootstrap. Questo
è un confronto di superfici di sola lettura, non un nuovo test permission/write.
Analizzare `legacyHspdkContext` dai report sincronizzati senza richiedere allegati.
Nuvio non è stato aggiunto; nessuna scrittura TV eseguita in questa fase.

---

## RICERCA — Legacy HSPDK launch/runtime context — 2026-09-26

Questa fase NON ripete il confronto HSPDK tra vidaahub e Smartone. Il dato reale già acquisito resta che una normale pagina browser e un vero store-app launcher context non ricevono automaticamente `HiBrowser / loadLibrary / Hisense.File`. La ricerca qui serve esclusivamente a identificare nomi e host storici concreti da cercare in modo read-only sul runtime corrente.

### Fonte primaria: hisense-app-store

Repository verificato:
- https://github.com/hisense-app-store/hisense-app-store.github.io
- file: `assets/js/lib.js`

Il codice storico:
- preferisce `window.HiBrowser`, con fallback a `window.Hisense`;
- chiama `loadLibrary('libhspdk-jsx.so')`;
- usa `File.read(path, 1)` e `File.write(path, ..., 1)`;
- legge `launcher/preset.txt` e `launcher/Appinfo.json`;
- scrive `launcher/Appinfo.json`.

`index.html` è una normale pagina web e `browser.html` è una pagina che naviga a un URL con `window.location`; il repository non crea lato JavaScript `HiBrowser`, `Hisense.File` o `loadLibrary`. Il binding deve quindi essere fornito dal browser/runtime host.

### Fonte primaria: vecchio launcher Hisense — nomi di componenti reali

Repository verificato:
- https://github.com/giofrida/Hisense-Smart-TV-Enhancements
- README: progetto per modelli Hisense 2016/2017, testato dall'autore su H43M3000;
- file principali:
  - `UI/hisenseUI/main.js`
  - `UI/hisenseUI/modulePages/appPages/hiBrowser.js`

Nel launcher storico esistono tre target App Manager concreti e distinti:

```text
hi_browser
lau_browser
tv_store
```

`main.js` contiene realmente:

```text
:am,am,hi_browser:start=hi_browser
:am,am,hi_browser:start=[hi_browser,-u,<url>]
:am,am,lau_browser:start=[lau_browser,-u,<url>]
:am,am,tv_store:start=...
```

`hiBrowser.js` identifica inoltre il componente con:

```text
amName: "hi_browser"
```

e lo arresta con un comando `:stop=hi_browser`.

Lo stesso vecchio codice launcher usa in più punti `Hisense.File.read/write`, incluso `launcher/Appinfo.json`. Questo prova l'esistenza storica della famiglia File nel system UI di quella generazione, ma NON prova da solo che il processo `hi_browser` fosse l'oggetto che iniettava HSPDK e soprattutto NON prova che questi target esistano ancora su VIDAA 9.60 Q0707.

### Fonte primaria: host browser storico su filesystem

Repository verificato:
- https://github.com/giofrida/Hisense-Amazon-Enabler
- file: `README.md`

Un log reale riportato dal progetto, ottenuto avviando l'app Amazon su un vecchio Hisense, mostra il browser applicativo come:

```text
/3rd/internet_browser/browser
```

e documenta configurazioni sotto:

```text
/3rd/internet_browser/apps/amazon_ruby/bws_profile.ini
/3rd_rw/internet_browser/browser_config.ini
/3rd_rw/internet_browser/bws_profile.ini
```

Questi path costituiscono evidenza concreta di una storica browser-host family `internet_browser`. Non vanno interpretati come prova che gli stessi file/path siano presenti o raggiungibili sulla Q0707.

### Corroborazione 4PDA — launch context

Nel thread 4PDA A7300F/A7500F del marzo 2022, il codice `hisense-app-store` viene esplicitamente servito da un PC e aperto nel browser TV via HTTP; lo stesso autore del post successivamente indica che si può aprire direttamente `https://hisense-app-store.github.io/` nel browser TV. Sono testimonianze di terzi, non documentazione Hisense.

Altri post 4PDA dello stesso periodo riportano comportamento dipendente da modello/generazione e discussioni VIDAA 3/4: quindi il successo storico del sito non è trasferibile automaticamente al firmware Q0707.

Le query esatte effettuate per `PikaHub` + HSPDK/HiBrowser/libhspdk non hanno prodotto una nuova evidenza di launch context utile in questa fase; non basare test nuovi sul solo nome finché non emerge una URL/repository concreta.

Le query pubbliche esatte `V0000.09.60 + hi_browser`, `MTK9603 + hi_browser`, `VIDAA 9 + /3rd/internet_browser/browser`, `Q0707 + hi_browser/internet_browser` e `Odin/111 + hi_browser` non hanno restituito risultati pertinenti. Quindi al 2026-09-26 non esiste nelle fonti pubbliche trovate un collegamento verificabile tra questi host storici e la build Q0707/MTK9603 attuale.

### Conclusione di ricerca

Il candidato storico più concreto per il browser esplicito è ora:

```text
hi_browser
```

con contesti vicini documentati:

```text
lau_browser
tv_store
/3rd/internet_browser/browser
```

Questi sono marker trovati in sorgenti reali, non nomi inventati.

Stato sulla TV attuale:

```text
PRESENZA_SU_Q0707 = NOT_PROVEN
HSPDK_IN_HI_BROWSER = HISTORICAL_CANDIDATE_NOT_PROVEN_ON_Q0707
```

Per questo NON è stato eseguito alcun comando App Manager e NON è stato tentato di avviare `hi_browser/lau_browser/tv_store`.

### Implementazione Sidee: source-only legacy launch marker probe

`web/hspdk-context.js` è stato portato a schema version 2.

Il collector continua a essere descriptor-only/read-only e ora aggiunge:

```text
legacyLaunchContextMatches
```

Durante la scansione del source di funzioni già esposte cerca soltanto marker storici verificati:

```text
:am,am,hi_browser:start
:am,am,lau_browser:start
:am,am,tv_store:start
:am,am,:start=[hi_browser|lau_browser|tv_store
app_hi_browser
app_lau_browser
app_tv_store
amName: "hi_browser"
/3rd/internet_browser/browser
/3rd/internet_browser/apps/
/3rd_rw/internet_browser/
```

Ogni match viene marcato:

```text
evidence = HISTORICAL_LAUNCH_MARKER_ONLY
```

Il probe NON:
- chiama `sendAM`;
- avvia componenti;
- invoca getter sconosciuti;
- chiama `loadLibrary`;
- chiama `File.read/File.write`;
- inventa URL, app ID o API.

Il bootstrap Smartone/Duplecast incorpora già il contenuto corrente di `web/hspdk-context.js` e `client_build_id()` include quel file nel digest, quindi la nuova build è automaticamente cache-bound anche nei launch-context capture.

### Validazione locale

Verificati localmente:
- parsing JavaScript del collector v2 con `node --check`;
- harness VM con getter/native methods proibiti;
- rilevazione della coppia File ereditata invariata;
- rilevazione source HSPDK invariata;
- rilevazione del marker reale `:am,am,hi_browser:start=[hi_browser,-u,...]`;
- rilevazione del path storico `/3rd/internet_browser/browser`;
- nessun getter/metodo proibito invocato.

Il clone completo della repo dal container di verifica non era disponibile per risoluzione DNS esterna, quindi non è stato rieseguito lì l'intero unittest Python; il collegamento bootstrap è stato però ricontrollato direttamente in `sidee.py`: legge `web/hspdk-context.js`, lo incorpora inline e salva `window.SideeHspdkContext()`.

### Prossimo dato utile

Dopo pull/restart, un normale capture HSPDK può ora dirci anche se nel runtime Q0707 esiste già qualche funzione/namespace che contiene riferimenti ai componenti storici sopra.

Interpretazione:
- se `legacyLaunchContextMatches` è vuoto, non inventare il passo successivo e non lanciare nomi alla cieca;
- se compare un marker concreto, seguire esclusivamente quel path/funzione reale con un ulteriore probe descriptor/source-only;
- passare a qualsiasi lettura/scrittura legacy solo se appare davvero una superficie callable `File.read + File.write`.



---

## RISULTATO TV — legacy launch markers + App Manager bridge — 2026-09-26

Ultimo capture ricevuto dal branch `sidee-reports`:
- sessione: `sidee-20260926-182425-cbe7`;
- contesto: `VIDAAHUB_BROWSER_CONTEXT`;
- collector HSPDK: schema v2;
- `legacyLaunchContextMatches=[]`;
- `discoveredSurfaces=[]`;
- `HiBrowser` assente;
- `Hisense.File` assente;
- `Hisense.loadLibrary` assente;
- stato: `NO_FILE_PAIR_OBSERVED`;
- unico source match utile: `window.getInstalledAppJsonObj`, che usa il già noto `Hisense_FileRead('websdk/Appinfo.json', 6)`.

Conclusione verificata: nel normale browser Q0707 testato non è esposto alcun riferimento source/descriptor ai target storici `hi_browser`, `lau_browser`, `tv_store` o alla famiglia filesystem `/3rd/internet_browser/`. Non lanciare questi nomi alla cieca.

### Nuova evidenza storica più bassa nello stack

Nel sorgente reale del vecchio launcher Hisense `giofrida/Hisense-Smart-TV-Enhancements/UI/hisenseUI/main.js`, la funzione:

`sendAM(command)`

delega il comando App Manager a:

`modeljs.sendam(command)`

Lo stesso launcher usa poi `sendAM` per avviare `hi_browser`, `lau_browser` e `tv_store`.

Questo NON prova che `modeljs` esista su Q0707, ma fornisce un nome di bridge concreto trovato in codice Hisense storico, quindi è un candidato migliore dei target di processo lanciati alla cieca.

### Implementazione successiva: descriptor-only App Manager probe

`web/hspdk-context.js` è stato portato a schema v3 e ora cattura, senza invocare nulla:
- `window.modeljs`;
- descriptor di `modeljs.sendam`;
- eventuale source serializzabile di `modeljs.sendam`;
- descriptor/source degli eventuali globali `sendAM`, `asyncStartApp`, `startHiBrowser`, `startLauBrowser`, `startTVStore`;
- source marker `modeljs.sendam`, `asyncStartApp`, `startHiBrowser`, `startLauBrowser`, `startTVStore`.

Il report usa:
- `legacyAppManagerBridge`;
- `legacyAppManagerMatches`.

Regola: anche se `modeljs.sendam` compare callable, questa fase NON lo chiama. Prima si registra presenza, descriptor e source. Solo dopo un risultato reale si decide un test successivo separato e minimo.


---

## RISULTATO TV — App Manager legacy assente; passaggio a inventory bridge moderni — 2026-09-26

Capture reale schema v3 ricevuto dal browser Q0707:
- build match: true;
- `legacyAppManagerBridge.modeljs.status = ABSENT`;
- `legacyAppManagerBridge.sendam.status = ABSENT`;
- `sendAM = ABSENT`;
- `asyncStartApp = ABSENT`;
- `startHiBrowser = ABSENT`;
- `startLauBrowser = ABSENT`;
- `startTVStore = ABSENT`;
- `legacyAppManagerMatches=[]`;
- `legacyLaunchContextMatches=[]`;
- `discoveredSurfaces=[]`;
- stato HSPDK invariato: `NO_FILE_PAIR_OBSERVED`.

Conclusione: il vecchio App Manager JS `modeljs.sendam`, pur essendo verificato nel launcher Hisense storico, non è esposto nel normale browser VIDAA 9.60 Q0707 testato. Non usare `sendAM`/target legacy come prossima azione.

### Ricerca pubblica mirata successiva

Le ricerche GitHub per equivalenti moderni `Hisense_* startApp/launchApp/openApp`, `HiUtils_createRequest appStart/startApplication` e `syncExecute('hiutils', ... app ...)` non hanno prodotto una API browser moderna equivalente verificabile.

È emersa una API `launchapp` in progetti di controllo remoto Hisense via MQTT `ui_service`, ma appartiene al piano remote-control e non dimostra un bridge browser con permessi AppConfig/HSPDK superiori. Non usarla come bypass senza un motivo separato.

Nel progetto pubblico `weinzii/vidaa-edge`, lo scanner considera concretamente le famiglie:
- `Hisense_*`;
- `HiUtils_*`;
- `VIDAA*`;
- `TvInfo*`;
- `vowOS`;
- `omi_platform`.

Questi nomi coincidono in parte con superfici già osservate sulla TV, quindi sono una base concreta per un inventario read-only del runtime attuale.

### Implementazione Sidee — modern bridge inventory schema v4

`web/hspdk-context.js` è ora schema v4 e aggiunge `modernBridgeInventory`.

Il collector registra senza invocare:
- globali il cui nome inizia con `Hisense_`, `HiUtils_`, `VIDAA`, `TvInfo`, `vowOS`, `omi_`, `opera_omi`;
- descriptor e source serializzabile delle funzioni;
- shape descriptor-only dei namespace esatti:
  - `vowOS`;
  - `omi_platform`;
  - `opera_omi`;
  - `TvInfo_Json`.

Limite massimo inventario globali: 250. I nomi sensibili già filtrati dal collector restano esclusi. Nessun getter o metodo viene invocato.

Validazione locale:
- `node --check` passato;
- smoke VM passato;
- funzioni mock native proibite non invocate;
- inventory rileva correttamente `Hisense_*`, `HiUtils_*`, `vowOS`, `omi_platform`, `opera_omi`, `TvInfo_Json`;
- source marker legacy continua a funzionare.

Prossimo dato utile: pull/restart Sidee e un solo `Inspect HSPDK Context (read-only)`. Analizzare `legacyHspdkContext.modernBridgeInventory` e seguire esclusivamente i nomi/metodi realmente presenti sulla Q0707.


---

## RISULTATO TV — modern bridge inventory e vowOS.store — 2026-09-26

Capture reale schema v4 dal browser Q0707:
- build match: true;
- `omi_platform` presente;
- `opera_omi` presente;
- `vowOS` presente;
- `vowOS.service`, `vowOS.tvinfo` e soprattutto `vowOS.store` presenti come oggetti;
- `omi_platform.sendPlatformMessage` e `addPlatformEventListener` presenti;
- `opera_omi.sendPlatformMessage` e `addPlatformEventListener` presenti;
- HSPDK legacy ancora assente.

Wrapper moderni osservati che usano realmente `omi_platform.sendPlatformMessage`:
- `Hisense_LoginWithVIDAA`: `type=APPMessage`, `MsgType=account`, `action=loginWithVidaa`;
- `Hisense_GetUpdatesVerInfo`: `type=getUpdatesVerInfo`;
- `Hisense_PrintLogMessage`: `type=log`;
- `Hisense_CloseBrowser`: `type=closeOTTPage`, con `appname`;
- `Hisense_SendAppMessageEvent`: forza `type=APPMessage` e inoltra l'oggetto;
- enable/disable VKB tramite messaggi piattaforma.

Questo prova che il browser moderno possiede un canale IPC verso la piattaforma, ma NON prova ancora che esista un verbo install/open arbitrario. Non inviare action/type inventati.

Dato più promettente: `vowOS.store` è realmente presente sulla Q0707. È quindi prioritario rispetto a ulteriori tentativi HiUtils/fileWrite o ai nomi legacy `hi_browser/modeljs`.

### Strategia corrente

Obiettivo: trovare un percorso di installazione gestito dal sistema, evitando il gate `fileWrite`.

Ordine:
1. enumerare descriptor/source di `vowOS.store`, `vowOS.service`, `vowOS.tvinfo` senza invocare nulla;
2. se `vowOS.store` espone metodi concreti di install/open/update/list, seguire solo quei metodi e ricostruirne la semantica dal source;
3. in parallelo, mappare solo i message schema `omi_platform` già presenti nel runtime, senza indovinare action/type;
4. se emerge un percorso store/system per installare un URL/app, testarlo prima con un'azione innocua o un'app già installata e verificare il risultato reale;
5. solo dopo usare lo stesso percorso per una nuova app.

Se `vowOS.store` non espone operazioni utili e nessun message schema install/open emerge dal runtime, la conclusione diventa che il browser pubblico Q0707 non offre una via sideload browser-only evidente; a quel punto servirebbe un altro contesto privilegiato ufficiale, non ulteriore spoof di identifier.

### Implementazione Sidee schema v5

`web/hspdk-context.js` ora aggiunge `vowOSNamespaces` e inventaria in sola lettura:
- `vowOS.store`;
- `vowOS.service`;
- `vowOS.tvinfo`.

Per ogni namespace registra:
- descriptor del namespace;
- nomi delle proprietà;
- descriptor delle proprietà;
- source delle sole funzioni data-property quando serializzabile;
- `invoked=false`.

Nessun getter o metodo viene eseguito.


---

## RISULTATO TV — vowOS.store espone pkgmgr install — 2026-09-26

Capture reale schema v5 dal browser Q0707:

`vowOS.store` espone realmente:
- `getInstalledPkgs()`;
- `installApp(appinfo, callback)`;
- `sendPkgmgrRequest(api, args, appinfo, callback)`.

Source verificato:

`getInstalledPkgs()` chiama:

`vowOS.service.syncExecute('pkgmgr', {api:'getInstalledPkgs', args:''})`.

`installApp()` ha due rami:
1. se `appinfo.packageName` manca, ricade nel già noto `Hisense_installApp(...)`, quindi nel percorso AppInfo/fileWrite già bloccato dal 503;
2. se `appinfo.packageName` è presente, costruisce `{pkgName, version:'', appId}` e chiama `sendPkgmgrRequest('install', ...)`.

`sendPkgmgrRequest()` per l'install package usa direttamente:

`GET https://localhost:9888/service/pkgmgr?api=install&args=<encoded-json>`

e NON passa attraverso `HiUtils_createRequest('fileWrite', ...)`.

Dopo una risposta package con `response.ret=true`, il wrapper costruisce il path:

`file:///APPS/pkgs/<pkgName>/index.html`

e solo a quel punto chiama `Hisense_installApp(...)` per aggiungere/aggiornare la voce launcher.

Interpretazione importante:
- l'installazione fisica del package e la registrazione in AppInfo/launcher sono due fasi separate;
- è plausibile che `pkgmgr` possa avere capacità diverse dal servizio `hiutils`;
- NON è ancora provato che `pkgmgr install` accetti pacchetti arbitrari o che funzioni dal browser corrente;
- NON invocare ancora `install`: prima leggere i package installati e ricostruire formato/naming reali.

### Implementazione Sidee

Aggiunto un test separato:
`Inspect pkgmgr installed packages (read-only)`.

Chiama esclusivamente:
`vowOS.store.getInstalledPkgs()`.

Salva il risultato in:
`pkgmgrInstalledPackages`.

Non chiama:
- install;
- uninstall;
- fileWrite;
- Hisense_installApp;
- sendPlatformMessage mutanti.

Questo è il prossimo dato necessario per capire il formato reale dei package VIDAA e se la pista package manager è praticabile.


---

## RISULTATO TV — pkgmgr getInstalledPkgs reale — 2026-09-26

Il probe read-only `vowOS.store.getInstalledPkgs()` è riuscito realmente sulla Q0707:

`ret=true`, `code=0`, SDK `1.5.0`.

Sono stati restituiti 18 pacchetti reali, tra cui:
- `tv.vidaa.app.browser` — type `ns` — `APPS:pkgs/tv.vidaa.app.browser/CHA/`;
- `tv.vidaa.app.phoenix` — type `ns`;
- `tv.vidaa.app.operationui` — type `system`;
- `tv.vidaa.app.youtube` — type `native`;
- `tv.vidaa.jsservice.basic` — type `js`;
- `tv.vidaa.jsservice.system` — type `js`;
- `tv.vidaa.lib.odin` — type `native`;
- `tv.vidaa.app.tvbrowser` — type `web` — `APPS:pkgs/tv.vidaa.app.tvbrowser/`.

Il dato `tv.vidaa.app.tvbrowser` è particolarmente importante perché conferma che il package manager gestisce anche pacchetti web reali.

Il source già verificato di `vowOS.store.sendPkgmgrRequest('install', ...)` costruisce, dopo una risposta package riuscita:

`file:///APPS/pkgs/<pkgName>/index.html`

Questo è coerente con il path restituito da `getInstalledPkgs`.

Interpretazione verificata:
- `pkgmgr` è vivo e accessibile dal browser corrente;
- `getInstalledPkgs` è autorizzato nel normale contesto `vidaahub.com`;
- il package manager distingue tipi `web`, `native`, `ns`, `system`, `js`, `res`, `phony`;
- il ramo package install non riceve una URL dal wrapper browser, solo `pkgName`, `version`, `appId`;
- quindi la sorgente del package deve essere risolta/staged altrove oppure tramite stato interno al package manager;
- NON è ancora provato che `pkgmgr install` accetti un package arbitrario o che consenta sideload.

Le ricerche pubbliche mirate sui package name Q0707 e su `APPS:pkgs` non hanno prodotto documentazione utile.

Prossima pista:
1. ricostruire formato/staging di un package web già installato, partendo da `tv.vidaa.app.tvbrowser`;
2. cercare nel runtime già caricato riferimenti source a `pkgmgr`, `packageName`, `/APPS/pkgs/` e wrapper di download/staging;
3. evitare `pkgmgr install` finché non è chiaro da dove prende il package.


---

## IMPLEMENTAZIONE — tvbrowser package + pkgmgr source probe — 2026-09-26

Dopo il risultato reale `getInstalledPkgs()`, Sidee aggiunge un probe separato e read-only per ricostruire il package web già installato `tv.vidaa.app.tvbrowser`.

### Path scelto

Il package manager Q0707 ha restituito:

`APPS:pkgs/tv.vidaa.app.tvbrowser/`

e il source reale di `vowOS.store.sendPkgmgrRequest()`, dopo install riuscito, costruisce:

`file:///APPS/pkgs/<pkgName>/index.html`.

Per la lettura via `Hisense_FileRead` viene usata la conversione documentata nel codice pubblico `weinzii/vidaa-edge/src/app/services/file-exploration/file-scanner.service.ts`:

`/etc/profile -> ../../../etc/profile`

quindi il probe legge:

`../../../APPS/pkgs/tv.vidaa.app.tvbrowser/index.html`

con mode `0`, la stessa modalità usata da quel file scanner pubblico.

### Nuovo probe UI

Aggiunto pulsante:

`Inspect tvbrowser package (read-only)`.

Il probe:
- invoca solo `Hisense_FileRead(relativePath, 0)`;
- non chiama `pkgmgr install/uninstall`;
- non chiama `Hisense_installApp`;
- non esegue `fileWrite`;
- calcola hash e lunghezza del file letto;
- salva solo preview limitata a 32 KiB;
- estrae fino a 120 riferimenti HTML `src/href`;
- nello stesso passaggio scansiona solo il source già caricato delle funzioni globali e di `vowOS.store` per:
  - `pkgmgr`;
  - `packageName`;
  - `sendPkgmgrRequest`;
  - `/APPS/pkgs/`;
  - `getInstalledPkgs`.
- nessuna funzione trovata dalla scansione source viene invocata.

Il report viene salvato in:

`pkgmgrPackageProbe`.

Interpretazione attesa:
- se `index.html` è leggibile, seguire esclusivamente i file/manifest realmente referenziati da quell'HTML;
- se la lettura è vuota/negata, usare i source matches runtime per trovare un wrapper di staging/download;
- non tentare ancora `pkgmgr install` finché il meccanismo di origine/staging del package non è documentato da dati reali.


---

## NOTE OPERATIVA — stale report dopo tvbrowser probe — 2026-09-26

Dopo che l'utente ha eseguito il nuovo probe `Inspect tvbrowser package (read-only)`, `reports/latest.json` sul branch `sidee-reports` è rimasto invariato:
- `clientBuildId = app-34999fc05e52`;
- `updatedAt = 2026-09-26T16:53:46.152Z`;
- campo `pkgmgrPackageProbe` assente.

Quindi NON interpretare questo come risultato negativo del probe: il nuovo report non è arrivato a GitHub.

Verificato su `main`:
- il pulsante `pkgmgrPackageProbeBtn` esiste;
- il relativo handler `inspectTvBrowserPackage()` esiste;
- il report salva `state.report.pkgmgrPackageProbe`;
- `client_build_id()` include `web/app.js` e `web/index.html`, quindi una build che contiene il probe non può mantenere il vecchio digest.

Per evitare altri clic su una UI stale, Sidee ora esegue automaticamente il probe read-only del package `tv.vidaa.app.tvbrowser` una sola volta per ogni `CLIENT_BUILD_ID` quando la pagina viene caricata e le API necessarie sono presenti.

Chiave sessionStorage:
`sidee.pkgmgrPackageProbe.<CLIENT_BUILD_ID>`.

L'auto-probe:
- è read-only;
- chiama solo `Hisense_FileRead` sul package già installato;
- salva normalmente il report;
- non installa/rimuove/scrive package.


---

## RISULTATO ALLEGATO — tvbrowser index READ_EMPTY e path-form probe — 2026-09-26

Report reale allegato dall'utente, build:
`app-7abbfb3ccac3`, build match true.

`pkgmgrPackageProbe` ha eseguito:
`Hisense_FileRead('../../../APPS/pkgs/tv.vidaa.app.tvbrowser/index.html', 0)`

Risultato:
- returnedType: `string`;
- length: `0`;
- status: `READ_EMPTY`;
- nessun errore;
- nessun riferimento HTML.

Questo NON dimostra che il package non esista: `getInstalledPkgs` lo aveva già restituito come package reale. Dimostra solo che la conversione Linux-relative usata dal primo probe non ha prodotto contenuto leggibile.

I source matches del medesimo report riconfermano:
- `vowOS.store.getInstalledPkgs -> service.syncExecute('pkgmgr', ...)`;
- `vowOS.store.installApp` usa `packageName` e `sendPkgmgrRequest('install', ...)`;
- `sendPkgmgrRequest` usa `https://localhost:9888/service/pkgmgr`;
- dopo install riuscito costruisce `file:///APPS/pkgs/<pkgName>/index.html`.

### Probe successivo

Il probe tvbrowser ora testa, read-only, solo tre rappresentazioni del medesimo path già osservate o direttamente derivate da sorgenti reali:
1. `APPS:pkgs/tv.vidaa.app.tvbrowser/index.html`
   - forma namespace esatta restituita da `getInstalledPkgs`;
2. `/APPS/pkgs/tv.vidaa.app.tvbrowser/index.html`
   - forma filesystem implicata da `file:///APPS/pkgs/<pkgName>/index.html`;
3. `../../../APPS/pkgs/tv.vidaa.app.tvbrowser/index.html`
   - conversione usata dal file scanner pubblico vidaa-edge.

Tutte usano `Hisense_FileRead(..., 0)`.
Nessun filename alternativo viene indovinato.
Nessun install/uninstall/write viene eseguito.

Il report salva ogni attempt separatamente e seleziona il primo che restituisce contenuto.
