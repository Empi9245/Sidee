# Sidee — risposta aggiornata + prossima chat

Data: 2026-09-26

## Stato reale

Repository: `Empi9245/Sidee`  
Branch: `main`

Il test reale del trace dedicato a:

`category-ui.vidaahub.com`

è già stato effettuato e **non ha prodotto alcun DNS hit osservato** sul flusso VIDAA Store provato.

Quindi la priorità corrente non è ripetere lo stesso test, ma usare il nuovo:

`storeDomainDiscovery`

aggiunto dal commit:

`40f3149f356bb913f90ead04cf2a5ae4e6da30fb` — `feat: discover active VIDAA Store domains`

Il discovery è DNS-only e passivo. Osserva soltanto host VIDAA/Hisense mirati e lascia le risposte DNS normali/inoltrate senza aggiungere nuovi spoof.

## Compatibilità con il trace precedente

Il trace `storeCatalogTrace` per `category-ui.vidaahub.com` resta attivo e non è stato rimosso.

È stato verificato che il nuovo discovery non modifica:
- il proxy HTTPS Store;
- il certificato/SAN;
- il pass-through byte-for-byte;
- la redaction;
- gli eventi DNS/TLS/HTTP;
- le risposte DNS dei nuovi host scoperti.

È stato però trovato un possibile conflitto nel sistema di sync: Sidee usa un solo `REPORT_SYNC_PENDING`, quindi due report diversi generati nello stesso debounce potevano far sì che uno sostituisse l'altro prima del push di `reports/latest.json`.

Correzioni applicate:

- `aff70161da0e495a7879c3f720ad9d81509c7f20` — correla `storeCatalogTrace` e `storeDomainDiscovery`;
- `bd22e01d5ab02f34e9f7288403e6388254be0c77` — evita sync duplicati nel discovery;
- `732438a13b2a0c7ba790fcbd3c04993283e808ba` — test di regressione per evitare blind spot nel report.

Ora, se i due sistemi si attivano nella stessa esecuzione:
- un report trace include anche lo snapshot discovery già disponibile;
- un report discovery include anche lo snapshot trace già disponibile.

Quindi qualunque dei due finisca per ultimo in `reports/latest.json` conserva entrambi i segnali disponibili.

## Prossimo test TV

1. `git pull` sul PC.
2. Riavvia Sidee.
3. Lascia il DNS della TV puntato al PC Sidee.
4. Non aprire browser, Smartone o Duplecast.
5. Apri il **VIDAA Store ufficiale**.
6. Naviga home, almeno una categoria e una detail page.
7. Rimani nello Store abbastanza da generare le normali richieste DNS.
8. Non premere Install.
9. Chiudi lo Store e attendi il sync.

Il dato principale da leggere nel prossimo `reports/latest.json` è:

`storeDomainDiscovery`

In particolare:
- `status`;
- `hostCount`;
- `hosts[].host`;
- `hosts[].qtypes`;
- `hosts[].queryCount`;
- `firstSeen`;
- `lastSeen`.

Se nello stesso test dovesse comparire anche `storeCatalogTrace`, analizzare entrambe le sezioni insieme.

## Obiettivo della prossima chat

Rispondere a una sola domanda:

> Quale hostname Store/launcher chiede realmente la Q0707 quando apro il VIDAA Store ufficiale?

Solo dopo aver osservato un hostname concreto si decide se aggiungere per quell'host un trace TLS/HTTP dedicato.

Non fare ancora:
- injection Nuvio;
- modifica delle risposte Store;
- Install;
- AppInfo write;
- pkgmgr inventato;
- brute force HiUtils/OMI;
- ritorno ai vecchi test AppConfig/identity/HSPDK.
