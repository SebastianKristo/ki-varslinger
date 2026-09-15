# KI Varslinger og sikkerhet 2.1.0

## Nytt: Dørlys – blink ved åpning

Blinker `light.pultskjermer` etter bekreftet opplåsing og påfølgende åpning av døren. Standard er tre blink med 0,5 sekunder per av/på-trinn, og åpning innen 60 sekunder etter opplåsing. Alle verdiene kan endres i oppsettet.

- Egen av/på-bryter; starter avslått.
- Krever begge hendelser i riktig rekkefølge. Åpning alene, omstart, gjenopprettet kontakt eller utløpt tidsgrense gir ingen blinking.
- Én blinkesekvens per opplåsing; ingen overlappende blink fra integrasjonens oppsett på samme lys.
- Gjenoppretter av/på, rapportert lysstyrke og aktiv farge etterpå. Lysgrupper med medlemsliste gjenopprettes per medlem.
- Forsøker gjenoppretting også ved tjenestefeil, deaktivering, reload og kontrollert avslutning.
- Egne statusfelt for lys og siste fullførte blink.

Etter HACS-oppdatering og omstart: legg til **Dørlys – blink ved åpning** i **KI Varslinger og sikkerhet**. Velg lås, `sensor.inngangsdor` og `light.pultskjermer`. Angi dørsensorens faktiske råverdier for åpen og lukket, og slå på funksjonsbryteren.

Autolåsrettingene fra 2.0.1 og øvrige funksjoner følger med. Ingen fysisk lås eller lampe er betjent under utvikling; se TESTING.md.
