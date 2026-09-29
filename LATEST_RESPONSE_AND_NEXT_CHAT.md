# Sidee — prossimo test: Native Install API Surface

Data: 2026-09-29

## Risultato Store Static API Mapper

Sessione:
`sidee-20260929-151455-56a1`

Risultato:
- 18 fetch;
- 0 errori;
- 0 path `/api/...` ricavati;
- 0 URL install/download;
- gli host UI moderni rispondono HTTP 401 con `no signature found`;
- `appstore-vidaa` e `tvmodules-vidaa` rispondono 403.

Quindi il frontend/API Store è request-signed e non è leggibile anonimamente dal PC.

## Cosa sappiamo già

La pipeline browser classica è:

`Hisense_installApp / Hisense_installApp_V2`
→ `HiUtils_createRequest("installApplication", ...)`
→ gate AppConfig
→ Q0707: 503 permission check error.

Questo però non dimostra che lo Store ufficiale usi esattamente la stessa superficie privilegiata.

## Nuovo probe

Aggiunto pulsante:

**Map native install APIs (read-only)**

Legge solo function source/descriptors già disponibili nel runtime TV per:
- `Hisense_installApp`
- `Hisense_installApp_V2`
- `HiUtils_createRequest`
- funzioni `vowOS.store` con nomi/install references
- inventory pkgmgr

Non invoca nessuna funzione di install/download/write.

## Test

1. `git pull`
2. riavvia Sidee
3. apri Sidee dal browser della TV
4. premi **Map native install APIs (read-only)**
5. attendi il salvataggio/sync
6. dì `fatto native API`

Poi leggere:
- `nativeInstallApiSurface.conclusionHint`
- `nativeInstallApiSurface.exact`
- `nativeInstallApiSurface.vowStore.functions`
- `nativeInstallApiSurface.sourceInventory.matches`

Se emergono `installApplication`, `installPackage`, `downloadPackage` o un'altra API concreta, quella diventa il prossimo target di analisi.
