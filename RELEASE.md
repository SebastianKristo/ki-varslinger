# Varslinger og sikkerhet 2.0.0

Integrasjonen heter nå **Varslinger og sikkerhet** i Home Assistant og HACS. Repoet og domenet `ki_notifications` beholdes; eksisterende varsler og hovedbrytere videreføres.

Nye oppsett:

- **Autolås:** lås etter åpen → lukket på dørsensoren. Eget tallfelt for ventetid, eller eksisterende input_number-helper. Avbryter ved åpning/ukjent dørtilstand og sjekker låstilstanden før kommando.
- **Heimdall ↔ Alarmo:** toveis aktivering/deaktivering med ekkogjenkjenning. Kameraenes privacy mode følger bekreftet Alarmo-tilstand. Ingen automatisk endring fra et gammelt øyeblikksbilde ved oppstart/reload.
- **Ansiktsgjenkjenning – dørlås:** tre lokale webhooks, låsekode i HA-oppsettet og sensor for Sebastian/Rune/Cybele etter bekreftet opplåsing. POST/PUT, valgfri GET; HEAD utfører ingen opplåsing.

Sikkerhetsfunksjonene starter avslått. Legg til ønsket oppsett, kontroller rå sensorverdier, fyll inn kode og slå på funksjonsbryteren. Deaktiver gamle autolås-/synk-/webhook-automasjoner før nye funksjoner tas i bruk.

Koder og webhook-ID-er er ikke lagt inn i repoet. De fylles inn lokalt i Home Assistant. De medfølgende testene bruker simulerte enheter og har ikke låst opp en fysisk dør eller endret en fysisk alarm.
