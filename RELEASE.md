# KI Varslinger og sikkerhet 2.0.1

- Navnet er nå **KI Varslinger og sikkerhet** i Home Assistant og HACS. Domenet og eksisterende entitetsidentiteter beholdes.
- Rettet at en tidligere lagret ventetid kunne overstyre ny ventetid valgt i innstillingene. Endringer via tallentiteten huskes fortsatt etter omstart.
- Sikkerhetsstatus viser hvorfor autolåsen venter, inkludert feil dørverdier og utilgjengelig sensor/lås. Attributtene viser rå dørverdi, forventede verdier, låstilstand, ventetidskilde og planlagt låsetid.
- Status oppdateres når døren/låsen endres og nedtelling starter eller avsluttes.
- Tydeligere felthjelp for rå dørverdier og input_number som overstyrer ventetiden.

Etter oppdatering: start Home Assistant på nytt. Kontroller at Autolås-bryteren er på og at verdiene i oppsettet samsvarer med råverdiene for dørsensoren. Åpne og lukk døren for å starte en ny nedtelling. Oppstart eller aktivering mens døren allerede er lukket starter ikke nedtelling.

Den konkrete årsaken hos brukeren er ikke bekreftet uten faktiske sensorverdier. Se TESTING.md for lokal validering. Ingen fysisk lås er betjent i testene.
