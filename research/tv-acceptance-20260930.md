# Prova diretta Nuvio sulla TV — 30 settembre 2026

L'utente ha chiarito che le funzionalità vanno anche misurate sulla sua TV e ha
autorizzato test e controlli. La disponibilità di documentazione pubblica **non è
una condizione per osservare il comportamento della propria app**. Restano i
vincoli su devkit, MSX, partner e bypass. La ricerca vidaahub già svolta rimane
valida; questo esperimento verifica il port Nuvio, non attribuisce nuovi permessi
a un'origine LAN e non ripete inventario/cattura/probe AppConfig.

**Correzione successiva:** l'utente indica vidaa-edge, che usa il contesto
vidaahub per esporre API. Il suggerimento di aprire il sito pubblico con DNS
automatico non verificava quel meccanismo ed è ritirato.
[Analisi corretta](vidaa-edge-context-review-20260930.md).
Il test LAN qui descritto è secondario, ora **fermato** (solo il nostro PID 3712),
nessun report TV ricevuto. La richiesta di apertura della pagina Nuvio non è più
il prossimo test prioritario. Codice e fixtures restano conservati.

Controllo PC: ricevitore post-Store TCP :8080 PID 5676 preservato. UDP 53
preesistente PID 6844 identificato come Windows SharedAccess/ICS, non toccato.
Nessun nuovo DNS/TLS avviato. Le sezioni seguenti documentano la preparazione,
non una vera installazione o uno stato corrente di ascolto su :8181.

## Esperimento preparato e avviato, poi fermato

Sidee `nuvio_tv_check.py` serve il **dist Nuvio esistente** in
`D:\nuvio\nuviotvsmart\dist`, aggiungendo in memoria soltanto l'osservatore
`web/nuvio-tv-check.js`. Nessuna modifica al dist, nuovo bundle o SDK VIDAA. Il server è statico: non
implementa il proxy media del server Nuvio completo. Un errore su una funzione
che richiede quel proxy non prova incompatibilità del firmware.
URL TV: `http://192.168.1.5:8181/?wrapper=vidaa`.
Processo avviato nascosto: **PID 3712**, porta 8181. Non è stato fermato il
ricevitore post-Store su 8080. Nessun DNS/TLS, Git worker, install/uninstall,
AppConfig o accesso a file TV. Statici limitati al dist; traversal rifiutato.

Il dist è una build già esistente, non un nuovo build del commit Nuvio corrente:
`app.bundle.js` 3.122.054 byte, SHA256
`95fb5d5b7172a04426049afa8357de0e5bd2c35fca43aff22874b617ee6373d1`.
`/__sidee/status` registra hash del dist e dell'osservatore. I report selezionati
sono in `reports/nuvio-tv-check-latest.json`, locale ignorato da Git, solo dopo
una vera apertura del client. Nessun esito TV sintetico è stato salvato.

## Cosa misura e cosa non dimostra

- Avvio del vero Nuvio: presenza della radice/schermate UI, conteggi degli errori
  script/risorse e promise. Non registra messaggi di errore, account, URL media o
  contenuti personali.
- Telecomando: frecce, OK e Indietro ricevuti, codice, trusted flag e posizione
  strutturale del focus prima/dopo. Nessuna prevenzione dei tasti o modifica del
  focus Nuvio. Esclusi input/testo digitato; buffer massimo 24 eventi. Evento
  ricevuto e cambiamento di focus non provano da soli l'intera UX senza cursore.
- Segnali standard del browser: display mode, manifest, service worker API e
  controller, eventi beforeinstallprompt/appinstalled osservati passivamente.
  Non si invoca alcuna installazione o prompt e un evento del browser non prova
  registrazione nativa VIDAA.
- Un marker dedicato localStorage, non contenuti dell'app. Ritrovarlo in una
  successiva apertura prova solo quel dato nella stessa origine, **non risorse
  Nuvio persistenti né un riavvio reale**.

L'origine iniziale è HTTP LAN: se insecure, il mancato segnale PWA/service worker
è **inconclusivo per il firmware**, perché il contesto stesso può impedirlo.
Questo non ripropone HTTP LAN come alternativa privilegiata a vidaahub. Serve
a misurare UI/telecomando reali e registrare solo eventuali segnali positivi.
Launcher, installazione, reboot con PC/server spenti e playback restano prove
separate, da eseguire quando esiste un'app avviabile o un'importazione consentita.

## Stato e prossima azione

Alla preparazione: HTTP 200 per Nuvio, script osservatore presente, **nessun
report TV ricevuto**. All'utente è stato chiesto soltanto di aprire l'URL col
telecomando e provare frecce/OK/Indietro. Sidee non ha un controllo remoto TV
verificato; non fingere di poter aprire menu o riavviare fisicamente da qui.
La precedente richiesta dell'URL E-Manual non è necessaria per questa prova.

Dopo la ricezione: separare provenienza TV/PC, leggere errori e traiettoria del
focus, confrontare col funzionamento visibile, correggere il port se serve e
riprovare solo l'interazione interessata. Verificare quindi eventuali azioni
di installazione/import offerte **dalla normale interfaccia della TV**: non
richiede necessariamente una guida online. Una funzione di importazione trovata
può essere provata con una propria app minima, rispettandone i normali controlli.
Nessun tentativo per acquisire permessi negati o sostituire pacchetti di altre app.

Solo dopo un avvio effettivo dal launcher: chiusura, riavvio reale e UI con PC,
Sidee e server locale spenti, poi contenuto autorizzato. Cache/segnalibro non
vengono dichiarati una vera installazione. Nessun successo dei cinque criteri
è attribuito alla sola preparazione del server.

## Verifiche fuori dalla TV passate

Receiver su porta temporanea con directory report temporanea: serve dist reale
e osservatore, rifiuta traversal/install route e origine estranea, omette campo
account aggiunto alla fixture. Nessun report finto nella directory reports reale.
Osservatore con DOM fittizio: movimento focus, esclusione input/testo, omissione
del valore marker/messaggio di errore, segnali browser distinti e buffer limitato.
Sintassi JavaScript e controllo diff passati. Non sono test sul firmware.

Manuali ufficiali specifici 50E77NQ anche scaricati prima della correzione
dell'utente, conservati localmente in reports (PDF scansioni, 20/18 pagine).
Lettura visiva delle pagine EN 2 / IT 1: rimando all'E-Manual con ricerca e QR.
Non letti integralmente e non usati per concludere assenza di importatori.
