# Sidee — full capture senza Hotspot mobile

Data: 2026-09-29

L'utente non può usare Windows Mobile Hotspot.

## Configurazione consigliata

Usare il PC come gateway via Ethernet:

Internet del PC
→ Windows Internet Connection Sharing (ICS)
→ adattatore Ethernet del PC
→ cavo Ethernet
→ TV Hisense

Se il PC non ha Ethernet, usare un adattatore USB-Ethernet.

Una normale situazione PC + TV entrambi collegati allo stesso router NON basta per vedere tutto il traffico HTTPS della TV, perché la rete switched non inoltra quei pacchetti al PC.

Alternative valide:
- router/switch con port mirroring verso il PC;
- secondo adattatore/rete in cui il PC faccia realmente da router/gateway.

## Modifica Sidee

La card Full Network Capture ora ha un campo:

`TV IPv4 (optional)`

Quindi il full capture può partire direttamente dall'IP TV e non dipende dal DNS auto-detect.

Workflow Ethernet ICS:

1. `git pull`
2. collega TV alla porta Ethernet del PC;
3. in Windows abilita Internet Connection Sharing sulla connessione che porta Internet e condividila verso l'adattatore Ethernet collegato alla TV;
4. sulla TV usa rete cablata/DHCP;
5. trova l'IPv4 assegnato alla TV (pagina rete TV oppure `arp -a` sul PC);
6. avvia Sidee come amministratore;
7. nel campo Full Network Capture inserisci l'IPv4 TV;
8. premi `Arm / Start capture`;
9. sulla TV: Store -> Duplecast -> Install/Download;
10. al termine premi `Stop & analyze capture`;
11. dire `fatto full capture`.

Se Windows ICS occupa o interferisce con DNS/53, il full packet capture può comunque essere eseguito grazie all'IP manuale; il DNS Sidee non è necessario per avviare pktmon in questa modalità.

Output prioritario:
`fullNetworkCapture.summary.topologyClassification`

- `FULL_PATH_VISIBLE`: setup corretto;
- `DNS_OR_LOCAL_ONLY_LIKELY`: traffico TV non sta attraversando davvero il PC.
