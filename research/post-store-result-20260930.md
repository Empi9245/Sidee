# Risultato reale della lettura dopo lo Store

TV identificata dall'utente come Hisense 50E77NQ, Q0707. La pagina non ha letto
modello/firmware: questa identificazione viene dalla conversazione, non da una
nuova misura. Codice corrente Sidee main `5b3ea81`.

Fonte locale: `reports/post-store-20260930-120901-112525.json`, copia anche in
`reports/post-store-latest.json`, 4.281 byte, SHA256
`78b8bc5564464bc9d17b823b482d6b3d94cebfe7d22f31e094da21229841ab4f`.
Report completo locale/ignorato, nessun sync Git automatico.

- Timestamp della pagina: `2026-09-30T12:09:05.471Z` (14:09:05.471 Europe/Rome).
- Ricezione registrata: `2026-09-30T14:09:01.111526+02:00`.
- Origine: `http://192.168.1.5:8080`, HTTP, secureContext false.
- Host/Origin HTTP del ricevitore coerenti con l'origine dichiarata.
- `Hisense_getInstalledApps`: **UNAVAILABLE**, count sconosciuto, nessun target.
- `vowOS.store.getInstalledPkgs`: **READ_OK**, 18 voci, senza troncamento.

Le voci restituite sono browser, librerie/risorse Odin e media, servizi JS,
YouTube, operationui, phoenix, osconfig e componenti phony. Il browser TV è
`tv.vidaa.app.tvbrowser`, type `web`, versione `9.6.0-r20260706x`, percorso
`APPS:pkgs/tv.vidaa.app.tvbrowser/`.

Nessun nome restituito identifica Nuvio o Duplecast. Le 18 voci sono coerenti
con il numero e le famiglie di componenti del sistema già documentati nel
contesto del 26 settembre. Non è stato ricostruito un confronto byte-per-byte
dei due inventari/versioni; non dichiarare invariato ogni campo.

## Implicazioni e limiti

Il package web locale esiste, ma non emerge un formato/procedura autorizzata
di importazione di un'app propria. L'elenco pkgmgr non è l'intero registro delle
normali app Store. L'assenza di Duplecast in questo elenco non prova che la sua
installazione conservi soltanto un URL, né esclude icone/config/cache/altro storage.
L'elenco app non disponibile impedisce di associare i package al registro
attuale; la domanda sulla reinstallazione Duplecast resta inconclusiva.

L'API di elenco app manca in questa pagina/origine; i precedenti report
vidaahub avevano più API. Non è un confronto A/B con codice e contesto nativo
identici, quindi non attribuire la differenza sicuramente al solo hostname.
Quei precedenti test avevano comunque rifiutato install/write con AppConfig 503.
API esposte e permessi di importazione sono due risultati distinti.

Nessun nuovo tentativo di installazione/write, accesso a file TV, modifica DNS,
TLS o identità. Nessun dominio vendor impersonato per ottenere privilegi.
I cinque criteri Nuvio restano non verificati. Non ripetere questo inventario
senza cambiamento di stato utile; non aggiungere un'altra scansione globale.
