# Sidee — stato aggiornato

Data: 2026-09-26

## Risultato del test TV

Il passive Store domain discovery ha funzionato sulla Q0707.

Report:
- sessionId: `sidee-20260926-201849-a7b2`
- build: `app-8101f5dd0f50`
- buildMatch: `true`
- status: `QUERIES_CAPTURED`
- totalQueries: 20
- hostCount: 13

Host osservati:
- `iot-voice-eu.vidaahub.com`
- `rsc-mntz.vidaahub.com`
- `detail-ui-eu.vidaahub.com`
- `rpt-mntz-azure.vidaahub.com`
- `ter-jrnl-eu.vidaahub.com`
- `appstore-vidaa.vidaahub.com`
- `tvmodules-vidaa.vidaahub.com`
- `img.vidaahub.com`
- `home-ui-eu.vidaahub.com`
- `static-ui.vidaahub.com`
- `crtv-mntz.vidaahub.com`
- `recommend-ui-eu.vidaahub.com`
- `exc-jrnl-eu.vidaahub.com`

Non sono comparsi:
- `category-ui.vidaahub.com`
- host launcher `*.hismarttv.com` previsti dal discovery

## Interpretazione

Il flusso Store osservato usa concretamente host della famiglia `vidaahub.com`.

Il miglior candidato per il prossimo trace di trasporto è:

`detail-ui-eu.vidaahub.com`

Seconda priorità:

`appstore-vidaa.vidaahub.com`

Poi:
- `home-ui-eu.vidaahub.com`
- `recommend-ui-eu.vidaahub.com`

La funzione precisa di ciascun host va confermata con traffico reale; il naming è solo un indizio.

## Prossimo passo

Aggiungere un trace pass-through mirato per `detail-ui-eu.vidaahub.com`, mantenendo:
- risposte upstream invariate;
- nessuna persistenza di valori sensibili;
- query values non persistiti;
- request headers/body non persistiti;
- soli metadata di trasporto e summary JSON bounded.

Poi ripetere il test aprendo una detail page reale nel VIDAA Store ufficiale.
