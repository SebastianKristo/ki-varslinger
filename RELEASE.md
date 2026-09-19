# KI Varslinger og sikkerhet 2.3.0

- **Ansiktsgjenkjenning – sperre etter at døren lukkes:** en webhook låser ikke opp rett etter at døren er registrert lukket. Det tolkes som at noen nettopp gikk ut og låste bak seg.
- Nye valgfrie innstillinger på ansiktsgjenkjenningsoppsettet: dørsensor, sensorverdier for åpen og lukket, og **Sperretid etter at døren lukkes** (standard 60 sekunder, `0` slår sperren av). Velg en sperretid som er lengre enn ventetiden i Autolås.
- Kall i sperretiden, og kall mens døren rapporterer åpen, besvares med HTTP 409 og en forklaring. Ingen opplåsingskommando sendes, og **Sist låst opp av** endres ikke.
- Sperren nullstilles når døren åpnes. Ukjent eller utilgjengelig dørverdi sperrer ikke, så en sensorfeil setter ikke ansiktsgjenkjenningen ut av spill.
- **Sikkerhetsstatus** viser **Sperret etter lukking** og nye attributter `dorsperre_sekunder`, `dorsperre_igjen`, `dorsensor`, `dorverdi`, `siste_forsok` og `siste_forsok_tid`. Webhook-ID og låsekode inngår ikke.

Eksisterende oppsett beholdes. Uten valgt dørsensor er oppførselen uendret fra 2.2.0. Sperren lagres ikke over omstart; døren må åpnes og lukkes på nytt etter reload.

78 tester bestått i et isolert HA-miljø med simulerte tjenester. Fysisk lås, dørkontakt og kamera er ikke testet. Se TESTING.md.
