# KI Varslinger 1.1.0

Tre nye oppsett i integrasjonens brukergrensesnitt:

- **Værmelding – AI:** standard kl. 08 alle dager når Sebastian er hjemme. Daglig prognose, korrekte måleenheter, valgfri AI Task-entitet og et enkelt reservevarsel hvis AI feiler.
- **Home Assistant startet:** oppstartsvarsel med dato og klokkeslett. Standard 15 sekunders forsinkelse; reload av integrasjonen gir ikke oppstartsvarsel.
- **Dørlås fastkjørt:** varsel etter 60 sammenhengende sekunder i jammed. Avbrytes ved normal eller ukjent tilstand.

Hvert oppsett har egen av/på-bryter, testknapp, mottakervalg og iPhone-lyd. De tre nye oppsettene foreslår også Sebastian sin OnePlus når notify-handlingen finnes. Statusentiteten viser feil fra vær-/AI-kilder.

Eksisterende oppsett beholdes. Nye varseltyper legges til manuelt etter oppdatering og HA-omstart. Deaktiver tilsvarende gamle automasjoner etter testing. Oppsettet leser ikke de gamle input_select-lydvelgerne; sett lydfilnavnet i integrasjonens Alternativer.

Krever HA 2025.12.5 eller nyere. Testene bruker simulerte tjenester; telefonene og din valgte AI-leverandør er ikke kontaktet i testingen.
