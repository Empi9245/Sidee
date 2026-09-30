# Correzione: perché vidaa-edge usa vidaahub.com

30 settembre 2026. L'utente ha richiamato esplicitamente
[weinzii/vidaa-edge](https://github.com/weinzii/vidaa-edge).
Revisione letta: `94c3134911cbd4b813eea1f88c56819c0981518b`.

## Errore corretto

L'assistente aveva suggerito di aprire il sito pubblico con DNS automatico per
cercarvi un importatore. **Quel suggerimento non verifica il meccanismo del
progetto.** Nel modello descritto da vidaa-edge, vidaahub è il contesto usato per
ottenere esposizione delle API Hisense alla pagina locale del toolkit. La sua
raggiungibilità pubblica non è il prerequisito di quel modello. Un indirizzo IP
LAN o una PWA generica non sono un confronto equivalente di quel contesto.
Le richieste precedenti all'utente di usare DNS automatico o mandare l'E-Manual
non sono il prossimo test di questo meccanismo e vanno considerate ritirate.

Questo descrive il progetto, non concede nuovi permessi Q0707. Non sono state
attivate riscritture DNS/TLS, cambiati certificati o eseguite operazioni per
acquisire autorizzazioni negate. Restano esclusi bypass e sostituzioni Store.

## Sorgenti primarie lette

- [README](https://github.com/weinzii/vidaa-edge/blob/94c3134911cbd4b813eea1f88c56819c0981518b/README.md):
  attribuisce a quel contesto l'accesso alle API; implementazione sperimentale e
  dipendente dal firmware, non un portale pubblico di distribuzione.
- [Template installer](https://github.com/weinzii/vidaa-edge/blob/94c3134911cbd4b813eea1f88c56819c0981518b/src/app/pages/installer/installer.component.html),
  blob `a31681872c43d96a06c7385d0c22830fd276a0e2`, 220 righe:
  indica esplicitamente il dominio come requisito del metodo descritto.
- [Componente installer](https://github.com/weinzii/vidaa-edge/blob/94c3134911cbd4b813eea1f88c56819c0981518b/src/app/pages/installer/installer.component.ts),
  blob `a8bff3287242e012652247618de239ed123c3567`, 290 righe:
  determina disponibilità chiamando i controlli del servizio. Non ottiene un
  attestato di autorizzazione dal firmware.
- [Servizio gestione app](https://github.com/weinzii/vidaa-edge/blob/94c3134911cbd4b813eea1f88c56819c0981518b/src/app/services/app-management.service.ts),
  blob `e7c71b7c38cdc2afe9a29f521118c101d87f7957`, letto integralmente.

## Cosa prova il codice

Il ramo legacy chiama Hisense_installApp con URL e icon URL: interpreta callback
0 come successo e non usa il valore di ritorno immediato per contraddirlo.
Il ramo nuovo legge/modifica/scrive il registro app con HiUtils; crea una voce
che contiene URL e StartCommand remoti. Nessuna delle due routine trasferisce
il bundle Nuvio nello storage TV. Sono operazioni di registrazione di app web,
non una prova di package locale o di interfaccia disponibile a host spento.

I controlli isLegacyMethodAvailable/isNewMethodAvailable verificano l'esistenza
delle funzioni globali. **Funzione presente non equivale a scrittura consentita.**
Il metodo nuovo tratta una lettura fallita come elenco iniziale vuoto: non è una
procedura da riprodurre indiscriminatamente sul registro reale. Un errore di
lettura non autorizza a ricostruire o sostituire il registro di altre app.

Il repository non contiene qui l'implementazione firmware del controllo di
origine; non viene inventata una whitelist C++ o una nuova regola Q0707.

## Collegamento alle prove già fatte sulla Hisense

I report salvati del 25/26 settembre **erano già nel contesto vidaahub**, non
soltanto da IP LAN. Il 25: install legacy/V2 presenti, callback 0 ma return false,
risultato interno false e AppConfig 503. Il 26: write gate respinto e readback
identico. Date, build e hash in
[vidaa-context-comparison-20260930.json](vidaa-context-comparison-20260930.json).
Questo conferma che Sidee aveva raggiunto l'esposizione di API di quel contesto;
non prova che l'origine fosse sufficiente per le autorizzazioni richieste.

La domanda corretta resta se un cambio effettivo di bootstrap/API/operazione
supportata spieghi una differenza rispetto a quelle sessioni. Non è stato
individuato dal codice corrente un nuovo metodo autorizzato che elimini il 503;
non affermare però impossibilità universale. Una nuova prova deve distinguere
un'ipotesi concreta dai due percorsi già esauriti, senza riscrivere AppConfig o
impersonare altre origini per ottenere permessi negati. Il solo link a questo
repository non è una nuova evidenza di formato/import/storage locale su Q0707.

## Stato operativo dopo la correzione

Test Nuvio LAN secondario fermato: solo PID 3712, identità verificata. Nessun
report TV arrivato prima dello stop. Codice/fixtures conservati, nessun esito TV
attribuito. Ricevitore post-Store PID 5676 e Windows ICS PID 6844 preservati.
Non ripetuti inventario, cattura HTTPS o write gate. Il dist Nuvio è invariato.
Gli aggiornamenti documentali annullano il piano di navigazione pubblica DNS
automatico quale prossimo controllo del meccanismo vidaa-edge.
