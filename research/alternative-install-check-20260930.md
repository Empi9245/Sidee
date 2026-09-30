# Alternative: controllo circoscritto del 30 settembre 2026

Richiesta: trovare una soluzione installabile per Nuvio sulla Hisense 50E77NQ
Q0707, mantenendo i vincoli già registrati. Nessuna soluzione provata in questo
controllo; nessuna nuova operazione sulla TV.

## Nuova candidata da osservare: pagina integrata storica

L'indice del
[WebApp Development Technical Guide VIDAA](https://www.vidaa.com/wp-content/uploads/2020/12/WebApp_Development_Guide_for_VIDAA.pdf)
restituisce la sezione 2, Quick Deploying, pagina 6/61. Descrive la pagina interna
`hisense://debug`, con nome app, URL, icone e pulsante INSTALL; il campo app URL
richiede http/https e la guida parla di avvio dal launcher. È distinta dal
toolkit vidaa-edge e dall'app DevKit. Non viene dedotto che sia ancora presente
su Q0707 o che autorizzi un import locale.

**Limite della fonte:** il recupero diretto del PDF restituisce ancora 404.
È stata letta la sezione indicizzata, non recuperato né letto integralmente il
documento. Il percorso 2020/12 non stabilisce l'età esatta della revisione; la
data di pubblicazione mostrata dal motore non prova un aggiornamento firmware.
Non dichiarare che questa sia una procedura corrente per VIDAA 9.

Unica osservazione TV richiesta per questa candidata: aprire quell'indirizzo
nel Browser normale e riferire se compare il modulo o un errore, senza premere
INSTALL. Sidee non può navigare autonomamente i menu/browser di sistema.
La domanda è pending: non è arrivato un risultato TV. Era stata chiesta anche
la presenza di un comando normale di importazione propria nella gestione app;
nessuna risposta acquisita. L'assenza di risposta non è un esito negativo.

Non sono richiesti cambi DNS, SDK, override identità o origini, scritture di
registro, attivazione DevKit o menu di servizio. Se la pagina richiede DevKit,
chiavi partner o aggiramento di autorizzazioni, questa strada è esclusa.
L'apertura della pagina non equivale a installazione. Anche un modulo funzionante
per URL remoti non dimostra risorse locali o UI utilizzabile a host spenti.
La prova minima con launcher/telecomando e riavvio reale resta subordinata a un
meccanismo consentito concretamente offerto dalla TV; non è stato preparato un
nuovo payload di installazione per un formato ignoto.

## Candidata scartata: HiZ-Store

Letti integralmente README, app.js, appAdder.js e il file di riferimenti del
progetto [PhasedGapple/HiZ-Store](https://github.com/PhasedGapple/HiZ-Store),
revisione corrente `0f1f7482098b1e9ed50df9418d9043f31c08c8d1`, commit
`2026-06-13T10:21:43Z`.

Il README dichiara WIP e mancato supporto delle TV moderne. Il
[codice installazione](https://github.com/PhasedGapple/HiZ-Store/blob/0f1f7482098b1e9ed50df9418d9043f31c08c8d1/app.js),
blob `d4beafaa86b998fb849ba0cfe4f538de3e4ebb1d`, chiama Hisense_installApp e poi
la scrittura diretta del registro tramite HiUtils. Non offre una nuova procedura
di importazione delle risorse. Contiene riferimenti non definiti `appIcon` e
`stremio` nella funzione di scrittura e tratta callback 0 come installazione
riuscita. Correggere questi errori JavaScript non risolve il gate già osservato
sulla Q0707. Codice letto, non eseguito, né modificato o portato sulla TV.

## Controlli di distribuzione: conferme, non nuove possibilità

- API GitHub: [release 1.2.1](https://github.com/NuvioMedia/NuvioTVSmart/releases/tag/1.2.1),
  pubblicata `2026-09-28T16:36:35Z`; asset WGT Tizen, IPK webOS e quattro
  installer desktop. Nessun asset VIDAA in quella release. Non scaricati/eseguiti.
- [PR #1007](https://github.com/NuvioMedia/NuvioTVSmart/pull/1007): API corrente
  closed, merged false, closed_at `2026-09-25T21:02:43Z`, head
  `00cfecaa02e22d903b2d004ced58150527eda39f`. Era già correttamente documentato
  in VIDAA_FEASIBILITY.md; la pagina web indicizzata Open resta obsoleta.
  Il primo commento dell'assistente di questa verifica lo presentava erroneamente
  come correzione nuova ai documenti: corretto, è una conferma.
- [Sito ufficiale](https://nuvio.tv/#get), letto nel browser PC con Smart TV
  selezionato: mostra Samsung Tizen e LG webOS, link a NuvioMedia/NuvioWeb e guida.
  Nessuna distribuzione VIDAA presentata in quel pannello. Non è inventario della
  TV né prova universale di assenza in ogni Store/regione.
- `https://web.nuvioapp.space/`: il tool web ha restituito timeout; il GET normale
  dal PC con TLS verificato, `2026-09-30T14:39:58.674418+00:00`, URLError senza
  status HTTP. Esito corrente inconclusivo, non nuovo 522 e non prova di servizio
  spento. Il 522 precedente resta una misura storica distinta. Nessun test TV,
  account o contenuto inviato al servizio.

Nessun nuovo inventario/cattura/write gate, nessun server avviato o modificato,
nessuna modifica al bundle Nuvio. Modifiche locali e control/request.json preservati.
Tutti i criteri finali ancora non verificati. Non ripetere ricerche identiche in
attesa: il prossimo fatto è la risposta sulla normale UI TV, non un altro dominio
da impersonare o un nuovo test LAN.
