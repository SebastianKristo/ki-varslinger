# KI Varslinger og sikkerhet 2.2.0

- **Test blinking:** umiddelbar blinketest, også når automatisk blinking er av. Gjenoppretter tidligere lysinnstillinger.
- **Kontroller autolås:** kontrollerer oppsett og råverdier uten låsekommando.
- **Test autolås – lås etter ventetid:** starter nedtelling og kan faktisk låse. Krever aktivert autolås, gjenkjent lukket dør og ulåst lås. Avbrytes ved åpning, ukjent dørtilstand eller avslått funksjon.
- **Dørverdi gjenkjent**, **Døren er lukket** og **Låsen er låst** viser tolkningen av kildene. Ukjent tilstand blir ikke tolket som åpen eller ulåst.
- **Testresultat** viser siste testbeskjed og tidspunkt. Sensorene oppdateres også når automatikk er av.
- Rettet rekkefølge ved oppstart av blinkejobben slik at en rask test ikke overskriver sluttresultatet med «startet».

Knappene og sensorene legges automatisk til eksisterende oppsett etter HACS-oppdatering og omstart. Ingen ny konfigurasjon kreves. Kontroller fysisk at dørvisningen følger åpning/lukking; gjenkjent verdi betyr samsvar med konfigurasjonen.

74 tester og innlastingstest bestått i et isolert HA-miljø med simulerte tjenester. Fysisk lampe og lås er ikke testet. Se TESTING.md.
