# Sidee — analisi ultimo test + prossima pista

Data: 2026-09-26

## Risultato del test appena fatto

Il test è valido e ci dà un risultato netto.

Sessione:

```text
sidee-20260926-172629-e5b8
```

Build:

```text
clientBuildId = app-83be535b43a8
serverBuildId = app-83be535b43a8
buildMatch = true
```

Quindi non stiamo leggendo una pagina vecchia o una build cacheata.

Contesto reale del test:

```text
https://vidaahub.com/
VIDAAHUB_BROWSER_CONTEXT
firmware V0000.09.60A.Q0707
VIDAA U09.60
MTK9603
```

Il probe HSPDK ha concluso:

```text
writeCapability = WRITER_UNAVAILABLE
error = Neither Hisense nor HiBrowser exposed a usable legacy File.read/File.write surface
```

Questa volta **non abbiamo ricevuto un errore di permission sul write**.

Il punto è precedente: nel contesto browser `vidaahub.com` il vecchio writer proprio non viene esposto.

---

# Cosa ha trovato realmente il runtime

## window.Hisense esiste, ma è quasi vuoto

Nel report:

```text
window.Hisense
status = DATA
type = object
```

ma contiene soltanto le proprietà applicative visibili:

```text
log
VirtualKeyboard
```

Non risultano:

```text
Hisense.loadLibrary
Hisense.File
Hisense.File.read
Hisense.File.write
```

Quindi il semplice fatto che `window.Hisense` esista NON significa che sia il vecchio host object HSPDK completo.

## window.HiBrowser non esiste

Il report dice:

```text
window.HiBrowser = ABSENT
```

e di conseguenza sono assenti anche:

```text
HiBrowser.loadLibrary
HiBrowser.File
HiBrowser.File.read
HiBrowser.File.write
```

## libhspdk-jsx.so non può nemmeno essere caricato da questo contesto

Il test non ha chiamato:

```javascript
loadLibrary("libhspdk-jsx.so")
```

perché nessuno dei due host object espone `loadLibrary`.

Quindi:

```text
libraryLoad.attempted = false
```

non significa che la libreria non esista sulla TV.

Significa più precisamente:

**dal runtime vidaahub attuale non abbiamo una funzione nativa con cui chiederne il caricamento.**

## Nessuna superficie equivalente trovata nello scan

Il nuovo probe read-only ha scansionato:

```text
scannedGlobals = 1285
scannedFunctions = 1241
```

e:

```text
discoveredSurfaces = []
status = NO_FILE_PAIR_OBSERVED
```

Quindi non è stato trovato nemmeno un altro oggetto globale che esponga una coppia equivalente `File.read/File.write`.

Lo scan era marcato `truncated: true`, quindi non è una dimostrazione matematica che nessun oggetto possibile esista in tutto il runtime, ma è già un'indicazione forte: il vecchio bridge non è semplicemente nascosto sotto un nome globale ovvio.

## L'unico match concreto trovato porta ancora al nuovo stack

Il solo source match utile è:

```javascript
function() {
    const installedAppJsonStr =
        Hisense_FileRead('websdk/Appinfo.json', 6)

    ...
}
```

cioè:

```text
getInstalledAppJsonObj
  -> Hisense_FileRead
  -> websdk/Appinfo.json
```

Questo è coerente con tutto ciò che abbiamo già visto sulla Q0707:

- la lettura moderna esiste;
- il file `websdk/Appinfo.json` è leggibile;
- il write moderno passa invece dal gate AppConfig e riceve 503.

---

# Conclusione del test

La pista HSPDK **non è smentita in assoluto**.

È smentita in questo preciso contesto:

```text
VIDAAHUB_BROWSER_CONTEXT
https://vidaahub.com/
Q0707
```

In altre parole:

```text
OLD HSPDK WRITE API
≠
API automaticamente disponibile in qualunque pagina VIDAA
```

Il vecchio metodo richiedeva un runtime che iniettasse nativamente:

```text
HiBrowser
oppure
Hisense.loadLibrary + Hisense.File
```

e la nostra pagina `vidaahub.com` oggi non riceve quella superficie.

Questo è diverso dal 503 di HiUtils.

Per HiUtils:

```text
API PRESENTE
→ richiesta arriva al backend
→ permission denied
```

Per HSPDK nel test appena fatto:

```text
API NON PRESENTE
→ nessun File.write viene nemmeno eseguito
```

Questa distinzione è importante.

---

# Nuova verifica esterna: il vecchio codice conferma questa interpretazione

Ho ricontrollato il codice storico pubblico invece di affidarmi solo al riferimento del forum.

Nel repository:

```text
hisense-app-store/hisense-app-store.github.io
assets/js/lib.js
```

il vecchio App Store fa esattamente questo:

```javascript
if (typeof HiBrowser != 'undefined') {
    this._objH = HiBrowser;
} else if (typeof Hisense != 'undefined') {
    this._objH = Hisense;
}

if (this._objH) {
    this._objH.loadLibrary('libhspdk-jsx.so');
}
```

e poi:

```javascript
this._objH.File.read(path, 1)
this._objH.File.write(path, JSON.stringify(obj), 1)
```

sul registro:

```text
launcher/Appinfo.json
```

La cosa decisiva è che **quel sito non contiene codice JavaScript che crea `HiBrowser`, `Hisense.File` o `loadLibrary`**.

Li presume già presenti.

Quindi erano funzioni iniettate dal browser/runtime nativo della TV.

Questo combacia perfettamente col nostro risultato: sulla Q0707, nel normale contesto `vidaahub.com`, quella vecchia superficie non viene iniettata.

Ho trovato anche un progetto russo recente:

```text
Pika4ui/Pikahub
```

che usa direttamente:

```javascript
Hisense.File.read("launcher/Appinfo.json", 1)
Hisense.File.write("launcher/Appinfo.json", writedata, 1)
```

Anche qui il codice **presuppone che `Hisense.File` sia già fornito dal runtime**; non lo costruisce lato pagina.

Quindi il prossimo problema non è:

> come chiamare meglio File.write?

Il problema corretto è:

> in quale contesto VIDAA viene ancora iniettato Hisense.File / HiBrowser.File sulla nostra TV?

---

# La prossima prova più importante

NON passerei ancora a devkit.

NON tornerei agli identifier.

NON ripeterei il test HSPDK su `vidaahub.com`.

La prova più utile ora è confrontare la stessa superficie HSPDK nei **veri contesti app che abbiamo già ottenuto**:

```text
Smartone IPTV — app ID 1470
Duplecast — app ID 1876
```

Li avevamo già usati per studiare identity/AppConfig, ma il test HSPDK appena eseguito è avvenuto soltanto in:

```text
VIDAAHUB_BROWSER_CONTEXT
```

non in Smartone o Duplecast.

Quindi dobbiamo fare un nuovo confronto **descriptor-only/read-only** in entrambi i launch context e catturare:

```text
window.Hisense
window.HiBrowser
Hisense.loadLibrary
HiBrowser.loadLibrary
Hisense.File
HiBrowser.File
File.read
File.write
```

senza eseguire subito il writer.

### Se Smartone o Duplecast espongono File.read/File.write

Allora abbiamo un risultato molto forte:

```text
HSPDK_SURFACE_IS_CONTEXT_DEPENDENT
```

e possiamo fare lì il nostro test protetto:

1. leggere `launcher/Appinfo.json`;
2. backup immutabile;
3. whitespace-only write;
4. readback;
5. restore;
6. verifica byte-per-byte.

### Se anche Smartone e Duplecast NON espongono HSPDK

Allora possiamo restringere ancora:

```text
normale browser        -> no HSPDK
normale store web-app  -> no HSPDK
```

e la pista successiva diventa cercare un **componente di sistema / browser legacy / pagina built-in** che riceva il vecchio bridge.

Non devkit: un contesto già presente sulla TV.

---

# Un altro indizio che non va ignorato

Il report HSPDK registra come user agent della pagina:

```text
Mozilla/5.0 ...
WebViewer/7.0.15
```

mentre altre informazioni VIDAA identificano il browser come:

```text
odin
```

Questo non prova da solo nulla, ma suggerisce che il runtime web attuale ha strati diversi e che il vecchio HSPDK poteva appartenere a un browser/host legacy differente.

Quindi ora ha più valore confrontare i contesti reali che continuare a cercare un metodo JavaScript per "creare" `Hisense.File`: se il binding nativo non viene iniettato, JavaScript non può ricostruirlo semplicemente copiando l'API.

---

# Cosa penso in sintesi

Il test è utile, non è una strada morta.

Abbiamo scoperto che:

```text
HiUtils write
= presente ma bloccato da AppConfig

HSPDK write su vidaahub
= non presente nel runtime
```

Sono due problemi diversi.

E il secondo ci dà una nuova domanda molto più precisa:

```text
DOVE viene ancora esposto il vecchio writer?
```

La mia priorità sarebbe quindi:

```text
1. HSPDK probe in Smartone
2. HSPDK probe in Duplecast
3. confronto automatico dei tre contesti
4. solo se tutti e tre sono negativi:
   ricerca di un runtime/system context diverso
```

Questo è molto più informativo che continuare a battere contro il 503.

---

# Prompt per la prossima chat

Sto continuando il lavoro su `Empi9245/Sidee`, branch `main`.

Lavora direttamente sulla repo e committa su `main`.

**NON usare devkit.**

Continua sulla pista:

```text
WRITE diretto AppInfo
Hisense.File / HiBrowser.File
HSPDK
forum russo / vecchio Hisense App Store / PikaHub
```

ma NON ripetere il test HSPDK nello stesso contesto `vidaahub.com`.

## Prima di modificare

Leggi completamente:

- `AI_CONTEXT.md`;
- `README.md`;
- `LATEST_RESPONSE_AND_NEXT_CHAT.md`.

Poi controlla:

- HEAD reale di `main`;
- `web/app.js`;
- `web/hspdk-context.js`;
- `web/index.html`;
- `sidee.py`;
- `sidee-reports/reports/latest.json`.

## Ultimo report verificato

Sessione:

```text
sidee-20260926-172629-e5b8
```

Build match:

```text
app-83be535b43a8
```

Contesto:

```text
VIDAAHUB_BROWSER_CONTEXT
https://vidaahub.com/
V0000.09.60A.Q0707
```

Risultato:

```text
legacyHspdkWriteLab.writeCapability = WRITER_UNAVAILABLE
```

con:

```text
window.Hisense = presente
Hisense.loadLibrary = assente
Hisense.File = assente
window.HiBrowser = assente
discoveredSurfaces = []
NO_FILE_PAIR_OBSERVED
```

Non c'è stato un write denied HSPDK.

Il writer non era esposto, quindi `File.write` non è stato eseguito.

## Ricerca pubblica già verificata

Il vecchio repository:

```text
hisense-app-store/hisense-app-store.github.io
assets/js/lib.js
```

seleziona `HiBrowser` oppure `Hisense`, poi chiama:

```javascript
obj.loadLibrary("libhspdk-jsx.so")
obj.File.read(...)
obj.File.write(...)
```

sul registro:

```text
launcher/Appinfo.json
```

Il sito non crea questi oggetti: devono essere iniettati dal runtime nativo.

Anche:

```text
Pika4ui/Pikahub
```

usa direttamente:

```javascript
Hisense.File.read("launcher/Appinfo.json", 1)
Hisense.File.write("launcher/Appinfo.json", ..., 1)
```

quindi anche quella implementazione presume un binding nativo già presente.

## Obiettivo immediato

Voglio verificare se la superficie HSPDK è **context-dependent**.

Abbiamo già due contesti reali installati:

```text
Smartone IPTV — 1470
Duplecast — 1876
```

Aggiungi/rendi automatico un **HSPDK Context Comparison** read-only che, quando Sidee gira nei tre contesti:

```text
VIDAAHUB_BROWSER_CONTEXT
SMARTONE_APP_CONTEXT
DUPLECAST_APP_CONTEXT
```

salvi e confronti:

```text
window.Hisense
window.HiBrowser

loadLibrary descriptor
File descriptor
File.read descriptor/source
File.write descriptor/source

enumerated own properties
prototype properties
eventuali altri oggetti globali con File + read/write
userAgent/runtime
```

Non eseguire getter sconosciuti.

Non invocare `File.write` durante questa fase di discovery.

Non chiamare `loadLibrary` finché non hai prima salvato chiaramente che la funzione esiste.

## UI / test

Rendi semplice fare il test dalla TV.

Idealmente, entrando tramite Smartone o Duplecast, Sidee deve eseguire automaticamente il capture read-only e salvarlo nel report, così io devo soltanto aprire/riaprire l'app.

Il report deve permettere di confrontare chiaramente:

```text
VIDAAHUB
vs
SMARTONE
vs
DUPLECAST
```

senza perdere i risultati precedenti.

## Se trovi File.read + File.write in un app context

NON aggiungere Nuvio subito.

Esegui solo un test separato, esplicito e protetto:

1. leggere `launcher/Appinfo.json`;
2. creare backup immutabile;
3. verificare JSON;
4. cambiare solo whitespace;
5. scrivere;
6. leggere subito indietro;
7. ripristinare l'originale;
8. verificare hash e byte originali.

Solo se ottieni:

```text
WRITE_ALLOWED_AND_RESTORED
```

si passa successivamente all'inserimento di Nuvio.

## Se Smartone e Duplecast non espongono HSPDK

Non tornare a HiUtils/identifier.

Aggiorna la conclusione a:

```text
HSPDK_NOT_EXPOSED_IN_NORMAL_BROWSER_OR_STORE_APP_CONTEXTS
```

e continua cercando quale **contesto di sistema/browser legacy già presente sulla TV** possa iniettare:

```text
HiBrowser
Hisense.loadLibrary
Hisense.File
```

Usa solo evidenze concrete da codice/runtime.

Niente brute-force di nomi API.

Niente devkit.

## Cose già escluse

Non ripetere:

- DNS;
- HTTP vs HTTPS;
- raw IP;
- install legacy/V2;
- callback 0;
- identifier casuali;
- override 1470/1876/2568;
- semplice vero app identity;
- `Hisense_SupportAppConfig() === true`;
- stesso HSPDK test su `vidaahub.com`.

## Fine fase

Aggiorna `AI_CONTEXT.md` soltanto con nuovi fatti verificati.

Committa direttamente su `main`.

