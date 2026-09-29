# Sidee — prossimo passo: trovare l'API install Store

Data: 2026-09-29

Il baseline appena fatto NON è una nuova sessione: `reports/latest.json` è ancora `sidee-20260929-145316-dec1`, quindi non usarlo come confronto A/B separato.

## Nuova direzione

È stato aggiunto uno `Store Static API Mapper` che gira dal PC e tenta di ricavare i path/API reali direttamente dagli asset pubblici dello Store VIDAA.

Non usa il MITM della TV.

Usa:
- TLS ufficiale VIDAA;
- GET read-only;
- allowlist fissa degli host Store reali osservati;
- nessun cookie/token/credential della TV;
- limiti stretti su byte e numero di asset.

Cerca:
- `/api/...`
- `installApplication`
- `installApp`
- `download`
- `package`
- `pkgmgr`
- `configUrlDownload`
- `productCode`
- `appBundle`
- `appContentId`
- `signatureServer`

Il risultato viene salvato nel report come:
`storeStaticMap`

## Cosa fare

1. `git pull`
2. riavvia Sidee
3. apri il dashboard Sidee sul PC
4. premi **Run Store API mapper**
5. quando finisce, dì **fatto API**

Non serve fare nulla sulla TV per questo test.

Poi controllare:
- `storeStaticMap.apiPaths`
- `storeStaticMap.interestingUrls`
- `storeStaticMap.keywordSummary`
- `storeStaticMap.resources[*].keywordHits`
- eventuali errori/redirect.
