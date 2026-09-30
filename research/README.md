# Verifiche fuori dalla TV — 30 settembre 2026

[Controllo circoscritto di alternative](alternative-install-check-20260930.md)
storico: hisense://debug già provato, candidata ritirata. La fase corrente è
studio locale del codice, senza ricerche online.

[audit-vidaa-install-contract.mjs](audit-vidaa-install-contract.mjs) verifica due
wrapper store originali, vincolati all'hash del report del 25 settembre, con VM
e trasporto fittizio. Quattro scenari; package positivo può mascherare il launcher
negato. [Risultato](vidaa-install-contract-20260930.json), non una prova TV.
Esecuzione dalla radice: `node research/audit-vidaa-install-contract.mjs reports/sidee-session-20260925-195421-ff60.json`.
Niente rete, chiamate native o package reali. Argomenti/identità non esportati.

Nuovo riscontro sulle prove salvate:
[legacy, V2 e New su Q0707](install-methods-q0707-20260930.md).
Confronto esteso con operazioni backend e hash delle sorgenti dei wrapper TV.
Nessuna funzione catturata viene eseguita; nessun nuovo tentativo sulla TV.

Priorità: [correzione del contesto vidaa-edge](vidaa-edge-context-review-20260930.md).
Il consiglio DNS automatico/sito pubblico non verificava il meccanismo del toolkit.
La [prova Nuvio secondaria](tv-acceptance-20260930.md) è preparata ma ora fermata,
nessun report TV. Non sostituisce vidaahub; code/fixtures conservati. L'utente
consente prove empiriche; non confonderle con bypass di permessi o API esaurite.

Indagine corrente prioritaria:
[vidaahub-context-20260930.md](vidaahub-context-20260930.md).
[vidaa-context-comparison-20260930.json](vidaa-context-comparison-20260930.json)
riassume sei report TV già salvati con hash, date, build, API e permessi;
non è un nuovo report TV. Si rigenera con
`python research/compare-vidaa-contexts.py` dalla radice Sidee, senza rete o
scritture. Campi mancanti sono non registrati. Non esporta identificatori nativi
o credenziali. Rigenerazione e risultati verificati il 30 settembre.

Le fonti pubbliche della ricerca attuale sono state lette, non eseguite sulla TV.
L'audit seguente è storico e MSX resta escluso: non è una procedura da riproporre.

Questo audit distingue risposte tenute in memoria da risorse applicative
persistenti. Non modifica Sidee, DNS, Store, TV o Nuvio. Media Station X è
escluso dal percorso finale per scelta dell'utente; il risultato rimane utile
per non riproporre il suo BlobService come installatore locale.

`audit-msx-container.mjs` richiede una copia del JavaScript pubblico documentato
su <https://msx.benzac.de/js/tvx-plugin.min.js>. Non è inclusa nel repository.
Prima di eseguire il solo corpo BlobService revisionato, controlla SHA256
`7cf9daabeb7787094433f7958fed41d2bedc561496e987d01fc070c6a0183684`.
Un cambiamento della fonte interrompe il test e richiede nuova revisione.

Esecuzione, da questa directory:

```powershell
node audit-msx-container.mjs C:\percorso\tvx-plugin.min.js msx-container-audit-20260930.json
```

Il trasporto è fittizio; la risposta HTML e gli object URL sono sintetici.
Nessuna richiesta Internet, nessun server locale o esecuzione del plugin
intero. Verifica GET/POST, accesso nella stessa istanza, assenza della risposta
in una nuova istanza/contesto e revoca degli object URL con `clear`.
La ricevuta JSON riporta fonte, versione, hash, risultati e limiti.

Passato il 30 settembre. Non simula un riavvio del firmware, non misura
localStorage della TV e non esclude una persistenza separata implementata da
altri componenti. Non verifica launcher, telecomando o riproduzione Nuvio.

Fonti aggiuntive, endpoint Nuvio e manuale USB: `../VIDAA_FEASIBILITY.md`.
