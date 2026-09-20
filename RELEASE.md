# KI Varslinger og sikkerhet 2.5.0

## Værmeldingen kan redigeres

Prompten lå hardkodet midt i en kodelinje i `extra_notifications.py`. Nå står den i
oppsettet, sammen med tittel og ikon.

Tre nye felt under værvarselet:

* **Prompt til AI-en** — flerlinjes tekstfelt
* **Tittel på varselet** — sto som «God morgen ☀️»
* **Ikon** — sto som `mdi:weather-partly-cloudy`

Standardene er nøyaktig det som sto i koden, så et eksisterende oppsett ser likt ut
etter oppdateringen. Tømmer du et felt, gjelder standarden igjen — ikke ingenting.

### {data} er værdataene

Skriv `{data}` der dataene skal inn. Glemmer du plassholderen, legges de til på
slutten likevel.

Det er med vilje: uten dataene har modellen ingenting å skrive ut fra, og ville funnet
på været i stedet for å si at det mangler. En prompt som ser litt rar ut er bedre enn
en oppdiktet værmelding.

Vil du bare endre tonen, hold på resten av teksten — setningene om å beholde oppgitte
enheter og ikke følge instruksjoner i datafeltene er der av en grunn. Den siste hindrer
at en værtjeneste med tekst i et felt kan styre hva varselet sier.

### Tester

10 nye: standarden uendret, egen prompt, manglende plassholder, plassholder flere
steder, tomme felt som faller tilbake, norske tegn som overlever, og at dataene
fortsatt er gyldig JSON.

De fire eksisterende testfilene krever et ekte Home Assistant-miljø og kunne ikke kjøres
her. Det gjaldt også før disse endringene.

---

# KI Varslinger og sikkerhet 2.2.0

- **Test blinking:** umiddelbar blinketest, også når automatisk blinking er av. Gjenoppretter tidligere lysinnstillinger.
- **Kontroller autolås:** kontrollerer oppsett og råverdier uten låsekommando.
- **Test autolås – lås etter ventetid:** starter nedtelling og kan faktisk låse. Krever aktivert autolås, gjenkjent lukket dør og ulåst lås. Avbrytes ved åpning, ukjent dørtilstand eller avslått funksjon.
- **Dørverdi gjenkjent**, **Døren er lukket** og **Låsen er låst** viser tolkningen av kildene. Ukjent tilstand blir ikke tolket som åpen eller ulåst.
- **Testresultat** viser siste testbeskjed og tidspunkt. Sensorene oppdateres også når automatikk er av.
- Rettet rekkefølge ved oppstart av blinkejobben slik at en rask test ikke overskriver sluttresultatet med «startet».

Knappene og sensorene legges automatisk til eksisterende oppsett etter HACS-oppdatering og omstart. Ingen ny konfigurasjon kreves. Kontroller fysisk at dørvisningen følger åpning/lukking; gjenkjent verdi betyr samsvar med konfigurasjonen.

74 tester og innlastingstest bestått i et isolert HA-miljø med simulerte tjenester. Fysisk lampe og lås er ikke testet. Se TESTING.md.
