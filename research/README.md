# Verifiche fuori dalla TV — 30 settembre 2026

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
