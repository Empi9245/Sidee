# Sidee — conclusione HSPDK + prossima direzione

Data: 2026-09-26

## Risultato reale appena verificato

Non serve più impostare come obiettivo principale un confronto HSPDK completo a tre contesti.

Il test HSPDK read-only è già stato eseguito realmente dentro **Smartone IPTV**, non soltanto preparato nel codice.

Sessione valida:

```text
sidee-20260926-174114-61c3
```

Build:

```text
clientBuildId = app-83be535b43a8
serverBuildId = app-83be535b43a8
buildMatch = true
```

Contesto:

```text
SMARTONE_APP_CONTEXT
http://vidaa.smartone-iptv.com/
firmware V0000.09.60A.Q0707
```

Lo user agent è il runtime VIDAA/Odin reale:

```text
Chrome/111
Odin/111.5563.5.1
VIDAA/9.0
MTK9603
V0000.09.60A.Q0707
```

Quindi non è un test browser PC o un mock.

---

## HSPDK dentro Smartone

Il collector ha trovato:

```text
window.Hisense = presente
window.HiBrowser = assente
```

ma dentro `Hisense` risultano soltanto le superfici già viste:

```text
log
VirtualKeyboard
```

Sono assenti:

```text
Hisense.loadLibrary
Hisense.File
Hisense.File.read
Hisense.File.write
```

e, poiché `HiBrowser` è assente, sono assenti anche:

```text
HiBrowser.loadLibrary
HiBrowser.File
HiBrowser.File.read
HiBrowser.File.write
```

Il probe ha inoltre restituito:

```text
discoveredSurfaces = []
sourceMatches = []
status = NO_FILE_PAIR_OBSERVED
```

con circa:

```text
scannedGlobals = 1100
scannedFunctions = 1061
```

Il collector era descriptor-only/read-only: nessun getter sconosciuto, `loadLibrary`, `File.read`, `File.write` o funzione scoperta è stato invocato.

---

## Confronto con vidaahub

Il precedente test reale in:

```text
VIDAAHUB_BROWSER_CONTEXT
https://vidaahub.com/
```

aveva già dato:

```text
Hisense presente
Hisense.loadLibrary assente
Hisense.File assente
HiBrowser assente
discoveredSurfaces = []
NO_FILE_PAIR_OBSERVED
```

Ora Smartone, pur essendo un **vero contesto app lanciato dal VIDAA launcher** e pur ricevendo una identity nativa reale:

```text
appId = 1470
navigator.appIdentifier = app 1470
serviceIdentifier = non vuoto
Hisense_SupportAppConfig() = true
```

mostra esattamente lo stesso risultato HSPDK sostanziale:

```text
NO HSPDK FILE PAIR
NO loadLibrary
NO HiBrowser
NO alternative File.read/File.write surface
```

Questa è già evidenza forte che il vecchio writer **non viene semplicemente abilitato passando dal browser normale a una normale store web-app**.

---

## Serve ancora Duplecast?

Non lo userei come nuova fase principale.

Nei file verificati qui c'è il capture HSPDK completo di Smartone; non c'è un equivalente completo Duplecast da cui poter affermare matematicamente che anche lì il risultato sia identico.

Però sappiamo già, dai test precedenti, che Smartone e Duplecast:

- sono entrambi veri contesti app launcher;
- ricevono entrambi identity native;
- espongono lo stesso stack moderno `HiUtils / vowOS`;
- hanno entrambi `Hisense_SupportAppConfig() === true`;
- hanno entrambi fallito il no-op `fileWrite` moderno con lo stesso AppConfig 503.

Adesso Smartone dimostra anche che un vero store-app context non porta automaticamente con sé HSPDK.

Perciò:

```text
VIDAAHUB_BROWSER_CONTEXT -> NO HSPDK
SMARTONE_APP_CONTEXT     -> NO HSPDK
```

è già sufficiente per cambiare priorità.

Se Duplecast viene aperto e il capture automatico arriva senza fare lavoro aggiuntivo, vale la pena conservarlo come ulteriore conferma.

Ma **non fermerei la ricerca aspettando Duplecast e non costruirei un sistema di confronto a tre**.

---

# Conclusione aggiornata

La conclusione più corretta, senza sovrainterpretare Duplecast, è:

```text
HSPDK_NOT_EXPOSED_IN_TESTED_NORMAL_BROWSER_AND_STORE_APP_CONTEXTS
```

Più precisamente:

- il normale contesto browser `vidaahub.com` non espone il writer legacy;
- un vero contesto store app, Smartone 1470, non espone il writer legacy;
- quindi `Hisense.File / HiBrowser.File / loadLibrary` non dipendono semplicemente dal fatto di essere dentro una normale app installata.

Questo rende molto meno interessante continuare a provare normali web-app context una per una.

---

# Cosa conviene fare ora

La pista giusta è cercare **quale runtime di sistema o browser legacy già presente sulla TV** riceveva il binding HSPDK.

Non devkit.

Non tornare a:

- HiUtils;
- identifier spoofing;
- DNS;
- raw IP;
- install legacy/V2;
- callback 0;
- `Hisense_SupportAppConfig() === true`;
- altro no-op `websdk/Appinfo.json` nel browser normale;
- brute-force di nomi API.

La domanda ora è:

```text
Quale componente VIDAA già presente sulla TV usa ancora un host
HiBrowser / Hisense con loadLibrary + File?
```

---

# Direzione di ricerca consigliata

## 1. Cercare consumatori reali di HSPDK, non altre implementazioni web

Abbiamo già codice web che chiama:

```javascript
HiBrowser.loadLibrary("libhspdk-jsx.so")
Hisense.loadLibrary("libhspdk-jsx.so")
Hisense.File.read(...)
Hisense.File.write(...)
```

ma questo non ci dice chi crea il binding.

Ora serve cercare evidenze su **dove veniva aperto quel codice**:

- browser legacy Hisense;
- vecchio App Store / launcher store;
- pagina di sistema;
- media/browser shell;
- componente built-in che usa HSPDK;
- eventuali URL/scheme realmente documentati nel codice storico.

Priorità alle fonti:

```text
hisense-app-store
PikaHub / forum russo
vecchi bundle/app store Hisense
repo/fork che contengono libhspdk-jsx.so
codice che fa riferimento a HiBrowser come runtime object
```

Non serve un'altra copia di `File.write`: serve il **launch context**.

## 2. Cercare nel runtime solo superfici concrete

Se emergono dal codice storico nomi reali di:

- pagina;
- host;
- scheme;
- componente;
- app/system ID;
- browser mode;
- launcher command;

allora Sidee può fare un probe read-only mirato.

Non inventare URL, nomi API o app ID.

## 3. Se troviamo un contesto legacy concreto

Prima fase soltanto:

```text
descriptor-only capture
```

cercando:

```text
HiBrowser
Hisense.loadLibrary
Hisense.File
File.read
File.write
```

Nessun write automatico.

Solo se appare davvero `File.read + File.write` si passa al test protetto su:

```text
launcher/Appinfo.json
```

con:

1. read;
2. backup immutabile;
3. JSON validation;
4. whitespace-only change;
5. write;
6. immediate readback;
7. restore originale;
8. verifica hash/byte.

Successo valido soltanto:

```text
WRITE_ALLOWED_AND_RESTORED
```

---

# Nota importante sul test Smartone

Il capture Smartone dimostra anche una separazione interessante:

stack moderno:

```text
HiUtils_createRequest = presente
vowOS.service = presente
vowOSContext = presente
native app identity = presente
```

stack legacy HSPDK:

```text
HiBrowser = assente
Hisense.loadLibrary = assente
Hisense.File = assente
```

Quindi le due famiglie di bridge non sono la stessa superficie con nomi diversi.

Sul firmware Q0707 il normale store app context possiede il bridge moderno, ma non riceve automaticamente quello legacy.

Questo rafforza l'idea che HSPDK appartenesse a **uno specifico host/browser/system runtime legacy**, non genericamente a tutte le pagine/app VIDAA.

---

# Prossima chat

Continua su `Empi9245/Sidee`, branch `main`.

Lavora direttamente sulla repo e committa su `main`.

**NON usare devkit.**

Prima leggi:

- `AI_CONTEXT.md`;
- `README.md`;
- questo file;
- HEAD reale;
- `web/hspdk-context.js`;
- `sidee.py`.

Non rifare il confronto HSPDK vidaahub vs Smartone: è già concluso.

Dato reale nuovo:

```text
VIDAAHUB_BROWSER_CONTEXT
-> NO_FILE_PAIR_OBSERVED

SMARTONE_APP_CONTEXT
-> NO_FILE_PAIR_OBSERVED
-> Hisense presente ma senza File/loadLibrary
-> HiBrowser assente
-> discoveredSurfaces []
```

Smartone aveva contemporaneamente vera native identity e bridge moderno funzionante, quindi una normale store web-app non riceve automaticamente HSPDK.

Non perdere tempo a costruire un confronto a tre contesti.

Duplecast può essere usato solo come conferma passiva se un capture già esistente/successivo arriva automaticamente; non deve bloccare la nuova ricerca.

Nuovo obiettivo:

**identificare da evidenze concrete quale browser/runtime/componente di sistema legacy già presente sulla TV poteva iniettare `HiBrowser`, `Hisense.loadLibrary` e `Hisense.File`.**

Continua sulla pista:

```text
hisense-app-store
PikaHub
forum russo
libhspdk-jsx.so
HiBrowser
launcher/Appinfo.json
vecchio App Store Hisense
browser/runtime legacy
```

Cerca il **launch/runtime context**, non un'altra implementazione di `File.write`.

Usa solo nomi/path/scheme/app/componenti trovati realmente nel codice o nelle fonti.

Niente brute-force.

Se trovi un contesto concreto già presente sulla TV, implementa prima solo un probe descriptor/read-only.

Non eseguire write finché non appare davvero una coppia `File.read + File.write`.

Aggiorna `AI_CONTEXT.md` solo con nuovi fatti verificati e committa su `main`.
