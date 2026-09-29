# Sidee — prossimo test: Full TV Network Capture

Data: 2026-09-29

## Cosa è stato aggiunto

Sidee può ora usare Windows `pktmon` per catturare l'intero traffico della TV durante l'installazione Duplecast.

Dashboard:
- **Arm / Start capture**
- **Stop & analyze capture**

Il capture:
- si filtra sull'IPv4 della TV;
- registra pacchetto intero;
- salva ETL + PCAPNG + TXT in `captures/<captureId>/`;
- i file restano SOLO sul PC e `captures/` è gitignored;
- GitHub riceve soltanto il riepilogo `fullNetworkCapture`.

## IMPORTANTE — topologia

Con il setup vecchio, PC = solo DNS, la cattura NON può vedere normalmente HTTPS TV -> Internet.

Per il test completo la TV deve usare il PC come gateway.

Percorso consigliato:
1. attiva **Hotspot mobile di Windows** sul PC condividendo la connessione Internet;
2. collega la Hisense alla rete Wi-Fi dell'hotspot del PC;
3. fai in modo che il DNS della TV punti al PC/hotspot così Sidee continua a vedere le query DNS;
4. avvia Sidee come amministratore.

## Test

1. `git pull`
2. riavvia Sidee come amministratore
3. TV collegata all'hotspot Windows del PC
4. apri Sidee sul PC
5. premi **Arm / Start capture**
6. sulla TV apri Store -> Duplecast
7. premi **Install/Download**
8. resta nello Store fino alla fine/errore
9. sul PC premi **Stop & analyze capture**
10. dì `fatto full capture`

Se all'arm Sidee non conosce ancora l'IP TV, resta ARMED e parte automaticamente alla prima query Store della TV.

## Dopo il test

Leggere `reports/latest.json -> fullNetworkCapture`.

Campi prioritari:
- `status`
- `summary.topologyClassification`
- `summary.httpsPacketRecords`
- `summary.originalBytes`
- `summary.topPeers`
- dimensione PCAPNG.

Se `topologyClassification = FULL_PATH_VISIBLE`, il setup è corretto e possiamo correlare i grossi trasferimenti con DNS/Store.

Se `DNS_OR_LOCAL_ONLY_LIKELY`, la TV non sta realmente attraversando il PC come gateway.
