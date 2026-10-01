# Installazione Nuvio su VIDAA — flusso v2

Questa integrazione importa il ricevitore e la pagina TV del pacchetto fornito,
li collega al comando principale di Sidee e usa il profilo `nuvio` già presente
in `config.json`. Il documento contenuto nello ZIP è stato trattato come materiale
di riferimento: comandi, indirizzi e affermazioni tecniche sono stati verificati
contro il progetto prima di essere adottati.

## Avvio

Su Windows esegui `start-windows-vidaa-v2.bat`. Il launcher avvia Sidee in modalità
isolata sulla porta HTTP 80 e, se esistono `.sidee-certs/vidaahub.com.crt/.key`,
anche su HTTPS 443 con lo stesso certificato auto-firmato (valido fino al
25 ottobre 2026): entrambi i canali servono la stessa pagina e condividono le
ricevute. Se Windows nega l'apertura della porta, avvia il file come
amministratore. Sulla TV apri uno dei due indirizzi già instradati dal progetto:

```text
http://vidaahub.com/
https://vidaahub.com/
```

Nessuna operazione nativa parte al caricamento della pagina. Le API del bridge
funzionano da entrambe le origini; HTTPS è il contesto storico in cui le
funzioni Hisense sono state osservate per prima su questa TV e copre il caso
in cui il browser TV passi da solo a `https://`.

## Le tre fasi

1. **Analizza funzioni** rileva le primitive disponibili, legge
   `websdk/Appinfo.json`, osserva il canale pkgmgr (`vowOS.store.getInstalledPkgs`)
   e registra come la pagina arriva all'identità inviata al bus
   (`vowOS.service.getIdentifier`, descriptor di `navigator.appIdentifier`,
   risultato nativo di `vowOSContext.getAppIdentifier`). Salva sul PC un
   report contenente il backup. Il pulsante di installazione si abilita
   soltanto se il registro è JSON valido, contiene `AppInfo` e il backup
   completo è stato ricevuto.
2. **Installa Nuvio** rilegge il registro, interrompe l'operazione se è cambiato
   dopo il backup, sostituisce soltanto l'eventuale voce con lo stesso ID e conserva
   le altre voci e gli altri campi del documento. Prova le primitive disponibili
   nell'ordine previsto dal pacchetto: scritture dirette del registro, poi
   `HiUtils fileWrite` (noto 503 AppConfig), poi il **canale pkgmgr** — mai
   misurato su Q0707 — prima con un pacchetto inesistente (prova di canale,
   atteso rifiuto senza effetti) e poi con `tv.vidaa.app.tvbrowser`, pacchetto
   reale già installato (nessun download previsto). Il ramo package di
   `vowOS.store.installApp` parla con il servizio `pkgmgr`, distinto da
   `installApplication`/`hiutils` dove il 503 è noto. Considera attendibile
   soltanto la rilettura del registro.
3. **Verifica dopo riavvio** rilegge il registro e controlla che l'ID configurato
   sia ancora presente. Il risultato riguarda il registro; la comparsa e il
   funzionamento della tile vanno confermati sulla TV.

I report sono salvati in `reports/vidaa-install-v2-<fase>-<timestamp>.json`; il
puntatore più recente è `reports/vidaa-install-v2-latest.json`. L'esito
`ONLY_PKG_REGISTER_CALLED_UNVERIFIED` indica che il canale pkgmgr ha risposto
positivamente ma la voce non compare in `Appinfo.json`: dato chiave, perché i
pacchetti di sistema compaiono nel launcher da `pkgmgr`, non solo dal registro.

## Configurazione condivisa

La voce installata arriva esclusivamente da `config.json`:

```json
{
  "nuvio": {
    "app_id": "nuviodebug",
    "app_name": "Nuvio TV",
    "app_url": "http://192.168.1.5:4173/?wrapper=vidaa",
    "icon_url": "http://192.168.1.5:4173/assets/images/icon.png",
    "store_type": "store"
  }
}
```

Il manifest firmato dalla build include questi valori. Il ricevitore rifiuta un
report di installazione che descriva un target diverso.

## Modalità senza scrittura

`start-windows-vidaa-check-v2.bat` conserva la variante diagnostica su porta 8083.
Questa modalità raccoglie descrittori del browser e osservazioni manuali senza
chiamare API native della TV.
