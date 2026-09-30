# Legacy, V2 e New: diagnosi sulla 50E77NQ

30 settembre 2026. Firmware target `V0000.09.60A.Q0707`.
Analisi offline delle prove TV esistenti, senza nuove operazioni sulla TV.

## Risultato

Il rifiuto osservato di `Hisense_installApp_V2` non è un errore del tipo
dell'argomento: la chiamata supera il controllo JavaScript dell'oggetto e arriva
al backend `installApplication`, che risponde `ret:false`, codice `503`,
`client request permission check error, please check appconfig`.
Legacy raggiunge lo stesso backend e riceve lo stesso rifiuto.

**Il metodo New (File System) di vidaa-edge non è Hisense_installApp_V2.**
Sono tre percorsi da distinguere, non tre autorizzazioni dimostrate:

| Percorso | Implementazione osservata | Esito già registrato sulla TV |
| --- | --- | --- |
| Native legacy, `Hisense_installApp` | Argomenti separati → helper `writeInstallAppObjToJson` → `installApplication` | 25 settembre, vidaahub: lettura riuscita, install negata 503; callback 0 e return false |
| Native V2, `Hisense_installApp_V2` | Oggetto → `mapAppInfoFields` → stesso helper/backend | Stessa sessione: lettura riuscita, install negata 503; callback 0 e return false |
| Upstream New (File System) | Lettura/modifica/scrittura diretta del registro via HiUtils | La capacità di scrittura era già negata nel test no-op del 26 settembre in vidaahub, con readback identico; non eseguita di nuovo la routine upstream |

V2 cambia l'interfaccia JavaScript e la mappatura dei campi. Il nome V2 non
dimostra una seconda procedura con privilegi maggiori sul firmware target.
Non è stata stabilita la data di introduzione dei due wrapper.

## Prova riproducibile, senza nuovi tentativi di installazione

Il report `reports/sidee-session-20260925-195421-ff60.json` conserva sia le
sorgenti dei wrapper esposti dalla TV sia le tracce delle due chiamate.
SHA256 del report:
`ae3eb5fba6cafffe8a14bb3aae7493634b27612b61158bea16dc2ffb073e1fba`.
Origine registrata: `https://vidaahub.com`.

Per entrambe le chiamate la sequenza è:

1. `fileRead`: `ret:true`, `code:0`, SDK `1.5.0`;
2. `installApplication`: `ret:false`, `code:503`, SDK `1.5.0`, errore AppConfig;
3. callback esterna `0`, ritorno immediato `false`.

Nella sorgente V2 l'argomento non oggetto provoca invece callback `-1` e
ritorno `false` prima della chiamata al backend. La traccia reale esclude quel
ramo come causa di questo tentativo. Non prova che ogni validazione successiva
del payload sarebbe superata dopo un eventuale permesso legittimo.

Entrambi i wrapper chiamano `writeInstallAppObjToJson`; il suo codice serializza
i metadati e chiama `HiUtils_createRequest('installApplication', ...)`, tornando
il campo `ret` del risultato. Nel ramo di aggiunta entrambi invocano callback
`0` anche quando quell'operazione fallisce. V2 ha inoltre un ramo di aggiornamento
che può ritornare `true` senza propagare il risultato della scrittura: non è
stato eseguito né usato come alternativa.

Hash SHA256 delle sorgenti conservate nel report:

| Funzione | SHA256 |
| --- | --- |
| Hisense_installApp | `81ff4b79be7afd46bf559b8b1b56fbf3b877721c6c8875a351c4d01ce8cc6ddd` |
| Hisense_installApp_V2 | `019c8e90c0300933b35faa6cbb80edd000663eef7948cd54394ddabec31399a6` |
| writeInstallAppObjToJson | `6b7f00e996593c455edd0975d04f120da7ffe5c77afdfb87136611b0b1566e5b` |

[compare-vidaa-contexts.py](compare-vidaa-contexts.py) ora riporta operazioni,
risultati e hash in
[vidaa-context-comparison-20260930.json](vidaa-context-comparison-20260930.json).
Non esegue le funzioni estratte; non esporta argomenti, registro o identità.
Il confronto è rigenerabile con Python usando esclusivamente i sei report locali.

Il percorso upstream New è descritto dal
[servizio alla revisione 94c3134](https://github.com/weinzii/vidaa-edge/blob/94c3134911cbd4b813eea1f88c56819c0981518b/src/app/services/app-management.service.ts),
già letto integralmente; dettagli e limiti in
[vidaa-edge-context-review-20260930.md](vidaa-edge-context-review-20260930.md).
Il test no-op dimostra il rifiuto di scrittura di quella sessione, non l'esecuzione
dell'intero installer upstream né il comportamento di ogni formato possibile.

## Cosa si può correggere e cosa resta da trovare

È correggibile il falso successo dell'installer: callback 0 o API presente non
devono essere presentate come app installata. I messaggi Nuvio erano già stati
corretti nella sessione; nessun nuovo bundle è stato generato. Un cambio della
forma dei parametri non è una soluzione dimostrata al rifiuto nativo osservato.
Non sono state alterate identità, AppConfig, firme o autorizzazioni.

Le routine lette registrano URL/metadati, senza trasferire il bundle Nuvio.
Anche risolvendo legittimamente il primo problema, occorrerebbe ancora dimostrare
la disponibilità dell'interfaccia con PC, Sidee e server locale spenti.
Questo limite del codice non è una nuova misura delle risorse attuali della TV.
Non ripetere l'inventario del 30 settembre o la cattura HTTPS già risolta.

L'alternativa compatibile con l'obiettivo è un importatore normale per una propria
app, oppure un contenitore consentito che conservi davvero le sue risorse.
Nessuno è stato individuato su questa Q0707 nelle prove disponibili. Un servizio
Nuvio gestito dal fornitore resta una strada distinta: serve sia endpoint operativo
sia avvio autorizzato, non soltanto una pagina raggiungibile. MSX/devkit/partner e
sostituzioni di app Store restano esclusi.

## Prossimo test decisivo e limite operativo

Il primo fatto nuovo utile sarebbe osservare nella normale UI TV una funzione
di importazione propria o un contenitore ammesso, con un percorso concreto.
Non è richiesta documentazione pubblica prima di questa osservazione. Sidee non
è un telecomando generale: il ricevitore corrente può ricevere i risultati della
pagina aperta sulla TV, ma non può autonomamente aprire e navigare i menu di sistema.
L'autorizzazione dell'utente ai test è già presente; manca una candidata concreta
e, per quel controllo dei menu, un canale di interazione disponibile.

Se emerge tale funzione, la prova è una app minima propria con versione visibile:
importazione normale, avvio dal launcher, frecce/OK/Indietro, riavvio reale con
host dell'UI spenti, riapertura e playback autorizzato. Un semplice ritorno true,
callback 0, bookmark o cache non soddisfa questi criteri.

Non è stata trovata una correzione che installi Nuvio; non affermare né successo
né impossibilità universale. Tutti i cinque criteri finali restano non verificati.
