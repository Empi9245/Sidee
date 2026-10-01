# Verifica dello ZIP Grok — 1 ottobre 2026

Le novità sono presenti nello ZIP, ma il nuovo codice non risulta integrato nei progetti locali Sidee e Nuvio. L'archivio contiene un'interfaccia React separata per diagnostica e registrazione di un URL Nuvio; non contiene il port completo del lettore Nuvio. Il risultato «VERIFIED INSTALLED» può essere prodotto interamente dal simulatore e non dimostra un'installazione sulla TV.

La richiesta non includeva un elenco di modifiche. Il confronto è quindi riferito alle funzionalità effettivamente presenti nell'archivio e ai progetti locali disponibili. Le istruzioni incluse nello ZIP sono state trattate come materiale da esaminare, senza eseguire le procedure suggerite.

| Funzione | Presenza nello ZIP | Limite verificato |
| --- | --- | --- |
| Interfaccia Home, Scansione, Installazione, Guida | Sì | Applicazione separata dai progetti locali |
| Italiano e inglese | Sì | Diversi messaggi di avanzamento restano solo in italiano |
| Scansione firmware, identità e registro app | Sì | In assenza dei wrapper nativi usa dati simulati; la presenza di un wrapper non prova i permessi |
| Pulsante FHD e tasto blu | Sì | La logica cambia il tipo di registrazione; non configura né misura la risoluzione video |
| Backup e ripristino | Sì | Backup di sessione, sovrascritto a ogni tentativo; il ripristino non verifica la rilettura |
| Gestione del rifiuto 503 e callback 0 | Parziale | Il rifiuto viene classificato correttamente; dopo il rifiuto vengono comunque eseguite altre fasi |
| Telecomando | Parziale | Gestisce blu, rosso e Indietro; non implementa spostamento del focus con le frecce |
| Profilo destinazione | Parziale | Tre preset; nessun editor dei campi del profilo |
| Installazione locale persistente del lettore Nuvio | Non dimostrata | Le destinazioni sono URL ospitati o LAN; nessun trasferimento delle risorse del lettore alla TV |

I difetti principali sono riproducibili fuori dalla TV:

1. **Il simulatore produce un successo presentato come installazione verificata.** Con FHD attivo e nessuna API TV disponibile, il risultato è `verified:true` e `VERIFIED INSTALLED`. Lo screenshot `install-ok.png` già incluso nello ZIP mostra la stessa situazione, con banner di anteprima e dettagli `SIM`. Il rilevamento usa la presenza dei wrapper: anche un ambiente con user agent TV e wrapper assenti sceglie il simulatore. Riferimenti: `src/lib/vidaa/bridge.ts:75`, `:155`; `src/lib/vidaa/install.ts:134`; `src/components/tv/install-view.tsx:99`.
2. **La verifica accetta un'app diversa con lo stesso nome.** Una rilettura con nome «Nuvio TV», ID diverso e URL diverso può comunque produrre `verified:true` quando il valore restituito dalla scrittura è positivo. Non verifica l'esatto stato richiesto, il launcher reale o il riavvio. Riferimento: `src/lib/vidaa/install.ts:122`.
3. **Manca la navigazione direzionale nel nuovo gestore del telecomando.** Tutte e quattro le frecce sono ignorate dal gestore. Non vi sono altre implementazioni di movimento del focus nei componenti TV esaminati. Un eventuale comportamento automatico del browser TV resta da verificare. Riferimento: `src/components/tv/use-tv-keys.ts:12`.
4. **Una callback mai ricevuta può lasciare l'operazione in attesa.** La promessa non ha timeout; la schermata mantiene lo stato occupato fino al suo completamento e non usa `finally` per ripristinarlo in caso di eccezione. Riferimenti: `src/lib/vidaa/bridge.ts:226`; `src/components/tv/install-view.tsx:26`.
5. **La simulazione FHD dipende anche dallo storico della sessione.** Dopo un primo successo con FHD attivo, un secondo profilo con FHD disattivo può ancora risultare installato: il simulatore valuta qualunque voce già presente con il tipo previsto, anziché solo la nuova richiesta. Riferimento: `src/lib/vidaa/bridge.ts:155`.

Le frasi della guida che suggeriscono una soluzione già disponibile sul firmware Q0707 non sono corroborate da nuovi risultati TV nello ZIP. I report locali esistenti documentano rifiuti AppConfig anche dai contesti delle app citate dalla guida. Non è stata acquisita alcuna nuova evidenza di permessi, launcher, persistenza dopo riavvio o riproduzione.

Nel Nuvio locale restano le modifiche preesistenti a `installer/index.html` e `scripts/package-vidaa.mjs`, che correggono i messaggi di successo e chiariscono che lo ZIP è un archivio web, oltre al documento `VIDAA_STATUS.md`. Le firme del nuovo codice Grok non compaiono nelle implementazioni locali esaminate. I 14 file sorgente selezionati dallo ZIP non esistevano nei percorsi corrispondenti dei due progetti prima della creazione di questa copia di audit.

La verifica ha eseguito otto scenari offline sul codice estratto, usando soltanto simulazioni o API fittizie. I risultati sono in `verification.json`; inventario e hash dell'archivio e dei file sono in `comparison.json`. Lo screenshot allegato è materiale già incluso nell'archivio, non una prova acquisita sulla TV durante questa verifica. Non sono stati eseguiti build completo, nuova verifica nel browser o test sulla TV. Nessuna modifica al codice dei due progetti, al DNS o ai servizi attivi; sono stati creati soltanto gli artefatti di audit in questa cartella.
