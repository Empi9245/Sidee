# Sidee — risposta aggiornata + prossima pista

Data: 2026-09-26

## Risposta aggiornata

Sì: continuiamo sulla pista **write diretto / AppInfo**, come nel materiale russo e in `weinzii/vidaa-edge`, **senza devkit**.

Il punto chiave è che il percorso moderno già testato:

```text
HiUtils_createRequest("fileWrite", ...)
  -> vowOS.service.syncExecute("hiutils", ...)
  -> localhost service
  -> AppConfig permission check
```

sulla tua VIDAA 9.60 arriva realmente al backend nativo, ma viene respinto con:

```text
ret: false
code: 503
client request permission check error, please check appconfig
```

Questo succede anche dentro veri contesti app VIDAA come Smartone e Duplecast. Quindi non conviene continuare a cambiare identifier, DNS, HTTP/HTTPS o app ID: quei test hanno già dimostrato che un'identità app reale non basta.

Il report più recente conferma inoltre che Smartone espone una vera identity nativa:

```json
{
  "appid": "1470",
  "md5": "42ffcf057e133f94c1b7b5cf543ef3bd",
  "permissions": ""
}
```

con:

- `vowOSContext.getAppId() = "1470"`;
- `getAppIdentifier()` reale;
- `vowOS.service.getIdentifier()` reale;
- `Hisense_SupportAppConfig() === true`.

Eppure l'exact no-op su `websdk/Appinfo.json` continua a ricevere il 503 e il readback rimane identico.

## Quindi la pista giusta ora è il writer legacy

Il codice attuale di Sidee contiene già la pista alternativa storica:

```text
window.Hisense / window.HiBrowser
        ↓
libhspdk-jsx.so
        ↓
File.read / File.write
        ↓
launcher/Appinfo.json oppure websdk/Appinfo.json
```

Questa è interessante perché **non usa direttamente `HiUtils_createRequest("fileWrite")`**.

Nel codice attuale `web/app.js` ci sono già:

- enumerazione sia di `Hisense` sia di `HiBrowser`;
- ricerca di `File.read` e `File.write`;
- fallback con `loadLibrary("libhspdk-jsx.so")`;
- tentativi separati sulle due superfici;
- prova prima di `launcher/Appinfo.json`, poi `websdk/Appinfo.json`;
- backup immutabile;
- probe con modifica di soli whitespace;
- readback immediato;
- restore esatto;
- verifica hash/byte prima di abilitare l'aggiunta di Nuvio.

La funzione importante è già:

```text
hspdkResolveWriter()
```

e prova concretamente entrambe le superfici, quindi non dobbiamo tornare alla vecchia logica "prendi il primo host object e fermati".

## HEAD reale attuale

Il branch `main` è attualmente su:

```text
e93275fa6c698ccd35afadbd5583b90d46ec540f
ui: add legacy HSPDK write lab
```

Il vecchio contenuto di questo file riportava un commit successivo `edaee...`, ma quell'HEAD non è quello reale di `main`. Da questo momento bisogna usare sempre l'HEAD reale del repository.

## Test da fare sulla TV

Dopo `git pull` e riavvio di Sidee, usa:

```text
Legacy Hisense File Writer
→ Test HSPDK Write + Restore
```

Il test deve restare questo:

1. rilevare `Hisense` e `HiBrowser`;
2. verificare se uno dei due espone già `File.read/write`;
3. se necessario chiamare `loadLibrary("libhspdk-jsx.so")`;
4. leggere un AppInfo valido;
5. salvare backup immutabile;
6. scrivere una variante JSON strutturalmente identica che cambia solo whitespace;
7. leggere subito indietro;
8. verificare che i byte siano realmente cambiati;
9. ripristinare i byte originali;
10. verificare restore esatto.

Solo se il risultato è:

```text
WRITE_ALLOWED_AND_RESTORED
```

ha senso usare:

```text
Add Nuvio via HSPDK
```

## Cosa dobbiamo leggere nel prossimo report

La prossima analisi deve partire da:

```text
sidee-reports/reports/latest.json
```

e controllare soprattutto:

```text
legacyHspdkWriteLab.beforeLoad
legacyHspdkWriteLab.afterLoad
legacyHspdkWriteLab.resolutionAttempts
legacyHspdkWriteLab.selectedOwner
legacyHspdkWriteLab.libraryLoad
legacyHspdkWriteLab.registry
legacyHspdkWriteLab.readAttempts
legacyHspdkWriteLab.probe
legacyHspdkWriteLab.restore
legacyHspdkWriteLab.writeCapability
legacyHspdkWriteLab.error
```

### Interpretazione

Se otteniamo:

```text
WRITE_ALLOWED_AND_RESTORED
```

abbiamo trovato un writer reale alternativo a HiUtils. A quel punto si può passare all'inserimento di Nuvio tramite lo stesso owner/path e verificare readback + launcher refresh.

Se otteniamo:

```text
Neither Hisense nor HiBrowser exposed a usable legacy File.read/File.write surface
```

la pista successiva non deve essere devkit e non deve tornare agli identifier: dobbiamo cercare **quale contesto o pagina di sistema carica davvero HSPDK** o espone un writer equivalente.

Se `File.read` funziona ma `File.write` no, è comunque un risultato importante: significa che il vecchio stack esiste ma il writer è separatamente protetto.

Se `launcher/Appinfo.json` è leggibile tramite HSPDK mentre `websdk/Appinfo.json` è quello usato da HiUtils, allora potremmo avere due registry/superfici differenti e va confrontato quale viene realmente usato dal launcher.

## Ricerca da fare solo se il test HSPDK non basta

Niente ricerca generica VIDAA. Solo stringhe concrete emerse dal runtime o dal materiale già individuato:

- `Hisense.File`;
- `HiBrowser.File`;
- `libhspdk-jsx.so`;
- `launcher/Appinfo.json`;
- `File.read`;
- `File.write`;
- eventuali altri nomi di librerie/bridge trovati nella sorgente;
- codice storico del forum russo;
- implementazioni concrete in `weinzii/vidaa-edge`.

L'obiettivo è trovare **un writer AppInfo alternativo al servizio HiUtils**, non un modo diverso di ripetere la stessa richiesta bloccata.

---

# Prompt per la prossima chat

Sto continuando il lavoro su `Empi9245/Sidee`, branch `main`.

Continua **solo sulla pista write/AppInfo**, come il forum russo e `weinzii/vidaa-edge`.

**NON usare devkit.**

Prima di modificare:

- leggi completamente `AI_CONTEXT.md`;
- leggi `README.md`;
- leggi `LATEST_RESPONSE_AND_NEXT_CHAT.md`;
- controlla l'HEAD reale di `main`;
- controlla `web/app.js`, `web/index.html`, `sidee.py`;
- leggi `sidee-reports/reports/latest.json`.

Non chiedermi di allegare il report se è già disponibile nel branch `sidee-reports`.

## Stato già verificato

Il percorso HiUtils:

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

anche dentro veri contesti Smartone/Duplecast.

Sono già esclusi come soluzione sufficiente:

- DNS;
- raw IP vs hostname;
- HTTP vs HTTPS;
- callback install `0`;
- `Hisense_installApp`;
- `Hisense_installApp_V2`;
- identifier JS inventati;
- app ID reali `1470`, `1876`, `2568`;
- vero launch context Smartone/Duplecast;
- `Hisense_SupportAppConfig() === true`.

Non ripetere questi test.

## Pista prioritaria

Analizza il test:

```text
Legacy Hisense File Writer
```

Sidee deve usare/provare:

```text
Hisense
HiBrowser
libhspdk-jsx.so
File.read
File.write
launcher/Appinfo.json
websdk/Appinfo.json
```

Il codice attuale possiede già `hspdkResolveWriter()`, che prova entrambe le superfici e il fallback `loadLibrary("libhspdk-jsx.so")`.

## Se il report mostra WRITE_ALLOWED_AND_RESTORED

Verifica prima che:

- il probe sia realmente stato letto indietro;
- il JSON sia rimasto strutturalmente identico;
- il restore sia byte-identico;
- il backup sia valido;
- il path e il selectedOwner siano chiari.

Solo dopo passa all'aggiunta di Nuvio tramite lo stesso writer e verifica:

- entry Nuvio presente nel readback;
- entry precedenti intatte;
- launcher refresh;
- presenza nel launcher/lista app.

## Se il writer legacy non è disponibile

NON tornare a HiUtils e NON usare devkit.

Continua cercando il contesto nativo reale che espone quel writer:

- quale app/pagina di sistema carica HSPDK;
- se `Hisense` e `HiBrowser` cambiano in base al contesto;
- se esistono altri host object concreti con `File.read/write`;
- se il forum russo mostra un bootstrap/libreria precedente alla chiamata `Hisense.File.write`;
- se `weinzii/vidaa-edge` o issue/fork contengono una seconda superficie di write oltre a `HiUtils fileWrite`.

Ricerca solo nomi e stringhe concrete osservate. Niente brute-force di API inventate.

## Regole per qualsiasi prova di scrittura

Ogni write deve:

1. leggere prima il file;
2. creare backup immutabile;
3. fare solo una modifica minima e reversibile;
4. leggere immediatamente indietro;
5. ripristinare l'originale;
6. verificare il restore byte-per-byte;
7. fermarsi se il contenuto non corrisponde.

Non usare reset, downgrade firmware, bootloader, partizioni, shell arbitraria o service-menu distruttivi.

Alla fine aggiorna `AI_CONTEXT.md` soltanto con nuovi fatti realmente verificati e committa direttamente su `main`.
