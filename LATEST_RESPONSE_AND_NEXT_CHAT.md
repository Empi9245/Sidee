# Sidee — risposta aggiornata + prompt per la prossima chat

Data: 2026-09-26

## Risposta aggiornata

Sì: da questo punto continuiamo sulla pista **write diretto / AppInfo**, senza devkit.

La direzione da seguire è quella vista sia nel materiale russo sia in `weinzii/vidaa-edge`: ottenere una scrittura reale del registro applicazioni della TV, ma senza continuare a perdere tempo con identifier casuali o con lo stesso `HiUtils_createRequest("fileWrite")` già bloccato dal firmware.

## Stato verificato sulla TV

TV:

- Hisense `50E70LEVS_0003`
- firmware `V0000.09.60A.Q0707`
- VIDAA U09.60
- MTK9603
- Chromium 111 / Odin

Abbiamo ormai verificato che:

- `https://vidaahub.com` funziona;
- raw-IP vs hostname non cambia il gate;
- HTTP vs HTTPS non cambia il gate;
- il browser vede realmente le API VIDAA;
- `HiUtils_createRequest` funziona per `fileRead`;
- `websdk/Appinfo.json` è leggibile;
- `Hisense_installApp` e `Hisense_installApp_V2` arrivano al backend nativo ma vengono respinti;
- `fileWrite` via HiUtils viene respinto;
- il callback esterno `0` non significa installazione avvenuta.

Errore reale comune:

```text
ret: false
code: 503
client request permission check error, please check appconfig
```

## Anche i veri contesti app non bastano

Sono stati provati due veri contesti creati dal launcher VIDAA:

- Smartone IPTV — app ID `1470`
- Duplecast — app ID `1876`

Entrambi espongono identity nativa reale, per esempio:

```json
{
  "appid": "1876",
  "md5": "...",
  "permissions": ""
}
```

e inoltre:

- `vowOSContext.getAppId()` restituisce l'app ID reale;
- `vowOSContext.getAppIdentifier()` restituisce un identifier nativo;
- `vowOS.service.getIdentifier()` restituisce lo stesso identifier;
- `Hisense_SupportAppConfig() === true`.

Nonostante questo, l'exact no-op:

```javascript
HiUtils_createRequest("fileWrite", {
  path: "websdk/Appinfo.json",
  mode: 6,
  writedata: exactRawPreviouslyRead
})
```

continua a tornare `503`.

Quindi il problema non è semplicemente "avere un vero app ID".

## Il bridge HiUtils è ormai abbastanza chiaro

Nel vero contesto Duplecast abbiamo letto la sorgente del wrapper.

Il percorso è:

```text
HiUtils_createRequest(type, msg)
  -> vowOS.service.syncExecute("hiutils", { api:type, args:msg })
  -> vowOS.service.executeHttpRequest(...)
  -> POST https://localhost:9888/service/hiutils
```

La richiesta aggiunge:

```text
header:
identifier: vowOS.service.getIdentifier()

body:
{
  "api": ...,
  "args": ...
}
```

e `getIdentifier()` delega a:

```javascript
vowOSContext.getAppIdentifier()
```

Non abbiamo trovato nel wrapper JS:

- MD5 aggiuntivo;
- permissions aggiuntive;
- StoreType;
- origin;
- AppInfo metadata;
- RoleID;
- CustomerID;
- firme;
- access code.

Quindi il gate `503` è quasi certamente sotto il wrapper JavaScript, nel servizio nativo / resolver AppConfig.

## Punto importante: non continuiamo più con identifier casuali

Sono già stati provati anche override concreti come:

- `1470`
- `1876`
- `2568`
- `16` TV Browser
- `164` APP STORE
- altri ID reali presenti sulla TV

Il risultato resta identico.

Conclusione verificata:

```text
IDENTIFIER_STRING_NOT_SUFFICIENT
```

Questa pista è esaurita.

---

# Nuova pista prioritaria: writer legacy HSPDK / Hisense.File

Il materiale storico/russo e le implementazioni vecchie mostrano una seconda famiglia di accesso ai file che NON passa necessariamente da:

```javascript
HiUtils_createRequest("fileWrite", ...)
```

La forma storica è invece simile a:

```javascript
Hisense.File.read("launcher/Appinfo.json", 1)
Hisense.File.write("launcher/Appinfo.json", raw, 1)
```

eventualmente dopo:

```javascript
Hisense.loadLibrary("libhspdk-jsx.so")
```

oppure attraverso `HiBrowser`.

Questa è la pista da seguire adesso.

È importante perché potrebbe essere un percorso nativo differente dal servizio `hiutils` che oggi ci risponde con `503`.

## Stato del codice Sidee

Prima modifica presente:

```text
e93275fa6c698ccd35afadbd5583b90d46ec540f
ui: add legacy HSPDK write lab
```

Quella versione aggiungeva il laboratorio HSPDK ma aveva un difetto:

sceglieva il primo oggetto trovato tra:

```text
HiBrowser
Hisense
```

e quindi poteva fermarsi sul wrapper sbagliato senza provare davvero l'altro.

Questo è stato corretto.

Nuovo HEAD:

```text
edaee8750188c382058d35f20ceeafda4df442f1
fix: probe both legacy VIDAA write surfaces
```

Ora Sidee:

- enumera sia `window.Hisense` sia `window.HiBrowser`;
- verifica separatamente se ciascuno espone `File.read` / `File.write`;
- prova `loadLibrary("libhspdk-jsx.so")` dove disponibile;
- non si ferma sul primo host object;
- seleziona la superficie che espone davvero il writer;
- salva nel report quale owner è stato usato;
- riusa lo stesso owner per restore e aggiunta;
- cerca i registri:
  - `launcher/Appinfo.json`
  - `websdk/Appinfo.json`

## Test HSPDK attuale

Il test non aggiunge Nuvio subito.

Fa prima:

1. individua `Hisense` / `HiBrowser`;
2. prova il caricamento HSPDK se serve;
3. trova un AppInfo leggibile;
4. crea backup immutabile sul PC;
5. costruisce una variante strutturalmente identica che cambia solo whitespace;
6. esegue `File.write(...)`;
7. legge immediatamente indietro;
8. verifica hash e byte;
9. ripristina ESATTAMENTE il backup originale;
10. verifica ancora hash e byte.

Solo se ottiene:

```text
WRITE_ALLOWED_AND_RESTORED
```

abilita:

```text
Add Nuvio via HSPDK
```

Quindi il test di scrittura resta reversibile e verificabile.

## Perché questa pista ha senso

`weinzii/vidaa-edge` usa direttamente:

```javascript
HiUtils_createRequest("fileRead", ...)
HiUtils_createRequest("fileWrite", ...)
```

e sulla nostra Q0707 quel percorso è chiaramente bloccato da AppConfig.

Il materiale storico invece usa il vecchio stack:

```text
Hisense / HiBrowser
  -> libhspdk-jsx.so
  -> File.read / File.write
```

Quindi non stiamo semplicemente ripetendo lo stesso test con un nome diverso.

Stiamo verificando se il firmware espone ancora una seconda superficie di filesystem che non passa dallo stesso permission resolver di `hiutils`.

## Cosa devi fare adesso sulla TV

Dopo:

```bash
git pull
```

riavvia Sidee.

Poi apri la pagina sulla TV e usa:

```text
Legacy Hisense File Writer
```

quindi:

```text
Test HSPDK Write + Restore
```

Non premere `Add Nuvio via HSPDK` manualmente se non viene abilitato dal test.

Il risultato che ci interessa è soprattutto:

- Host object
- HSPDK library
- Registry path
- Whitespace probe
- Restore
- Capability

Se il test salva il report normalmente, non serve allegare nulla: il prossimo step deve leggere:

```text
sidee-reports/reports/latest.json
```

## Interpretazione dei possibili risultati

### Caso 1

```text
WRITE_ALLOWED_AND_RESTORED
```

Questo è il risultato migliore.

Significa che Q0707 continua ad avere un writer legacy utilizzabile anche se `HiUtils fileWrite` è bloccato.

A quel punto Sidee può usare quel writer per inserire Nuvio nel registro e mandare il refresh launcher.

### Caso 2

```text
Legacy File.read/File.write not exposed
```

Significa che il vecchio stack HSPDK non è disponibile da quel runtime.

A quel punto bisogna capire se:

- il writer esiste solo in un contesto specifico;
- una pagina di sistema lo carica;
- l'App Store ufficiale usa un host object diverso;
- esiste un altro bridge legacy equivalente.

### Caso 3

```text
File.read funziona ma File.write non applica la modifica
```

Questo è comunque utile.

Vuol dire che anche la superficie legacy è separata in read/write e dobbiamo ispezire il suo backend o il contesto che la rende writable.

### Caso 4

```text
launcher/Appinfo.json
```

risulta leggibile mentre `websdk/Appinfo.json` non lo è tramite HSPDK.

Questo sarebbe un dato molto interessante, perché suggerirebbe che il vecchio writer opera su un registro differente da HiUtils.

---

# Prompt per la prossima chat

Sto continuando il lavoro su `Empi9245/Sidee`, branch `main`.

Lavora direttamente sulla repo collegata.

NON usare devkit.

NON tornare alla pista degli identifier casuali.

NON rifare test generici DNS / HTTP / HTTPS.

La pista prioritaria è:

```text
WRITE diretto AppInfo
Hisense.File / HiBrowser.File
HSPDK / libhspdk-jsx.so
```

Prima di fare qualsiasi modifica:

1. leggi completamente `AI_CONTEXT.md`;
2. leggi completamente `README.md`;
3. leggi completamente `LATEST_RESPONSE_AND_NEXT_CHAT.md`;
4. controlla l'HEAD reale di `main`;
5. leggi `web/app.js`;
6. leggi `web/index.html`;
7. leggi `sidee.py`;
8. leggi il report più recente da:

```text
sidee-reports/reports/latest.json
```

Non chiedermi di allegare il JSON se è già lì.

## HEAD noto

```text
edaee8750188c382058d35f20ceeafda4df442f1
fix: probe both legacy VIDAA write surfaces
```

Controlla comunque l'HEAD reale prima di assumere che sia ancora quello.

## Stato già escluso

Non perdere tempo con:

- `Hisense_installApp`;
- `Hisense_installApp_V2`;
- callback esterno `0`;
- DNS;
- raw IP;
- hostname;
- HTTP vs HTTPS;
- override JS di identifier;
- app ID `1470`;
- app ID `1876`;
- app ID `2568`;
- app ID APP STORE `164`;
- semplice launch dentro Smartone/Duplecast;
- `Hisense_SupportAppConfig() === true`.

Tutto questo è già stato provato.

## HiUtils è già caratterizzato

Il write HiUtils:

```javascript
HiUtils_createRequest("fileWrite", {
  path: "websdk/Appinfo.json",
  mode: 6,
  writedata: ...
})
```

riceve:

```text
ret:false
code:503
client request permission check error, please check appconfig
```

anche dentro veri contesti app VIDAA.

Non continuare a martellare questa API con identifier diversi.

## Obiettivo della prossima fase

Analizza PRIMA il risultato del nuovo:

```text
Legacy Hisense File Writer
```

in `reports/latest.json`.

Controlla in particolare:

- `legacyHspdkWriteLab.beforeLoad`;
- `legacyHspdkWriteLab.afterLoad`;
- `legacyHspdkWriteLab.resolutionAttempts`;
- `legacyHspdkWriteLab.selectedOwner`;
- `legacyHspdkWriteLab.registry`;
- `legacyHspdkWriteLab.readAttempts`;
- `legacyHspdkWriteLab.probe`;
- `legacyHspdkWriteLab.restore`;
- `legacyHspdkWriteLab.writeCapability`.

## Se HSPDK write funziona

Se:

```text
writeCapability = WRITE_ALLOWED_AND_RESTORED
```

allora verifica bene il report e solo dopo usa il percorso già previsto per aggiungere Nuvio tramite lo stesso writer.

Dopo l'aggiunta verifica:

- AppInfo readback;
- entry Nuvio presente;
- entry preesistenti intatte;
- launcher refresh;
- presenza dell'app nel launcher / lista installate.

## Se HSPDK non funziona

NON tornare indietro a HiUtils.

Continua sulla pista write cercando una diversa superficie nativa realmente presente sul firmware.

Ricerca mirata solo su stringhe concrete osservate, per esempio:

- `Hisense.File`;
- `HiBrowser.File`;
- `libhspdk-jsx.so`;
- `launcher/Appinfo.json`;
- `File.read`;
- `File.write`;
- eventuali nomi nuovi trovati nel runtime.

Controlla anche se una pagina/app di sistema già presente sulla TV espone la stessa API con un oggetto diverso.

La priorità è capire se esiste:

```text
un writer AppInfo alternativo al servizio hiutils
```

senza devkit.

## Regole di sicurezza per il test

Ogni prova di scrittura deve:

1. leggere prima il file;
2. creare backup immutabile;
3. fare una modifica minima e reversibile;
4. leggere immediatamente indietro;
5. ripristinare l'originale;
6. verificare il restore byte-per-byte;
7. non aggiungere Nuvio se la prova precedente non è stata verificata.

Non usare:

- reset;
- firmware downgrade;
- bootloader;
- service-menu distruttivi;
- scritture a partizioni;
- comandi shell arbitrari;
- setter RoleID/CustomerID inventati;
- firme/access-code casuali.

## Criterio di successo

La fase è utile se stabilisce almeno una di queste cose:

- `Hisense.File.write` funziona su Q0707;
- `HiBrowser.File.write` funziona su Q0707;
- il vecchio HSPDK writer usa un registro diverso;
- il vecchio writer esiste ma richiede un contesto specifico;
- il vecchio writer è stato rimosso/bloccato;
- emerge un altro writer nativo concreto da testare.

Alla fine aggiorna `AI_CONTEXT.md` solo con i nuovi fatti realmente verificati e committa direttamente su `main`.
