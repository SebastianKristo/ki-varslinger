# KI Varslinger og sikkerhet 2.7.0

## Live Activities

Varsler som blir stående på låseskjermen og oppdateres, i stedet for en rekke bannere – Live Activity på iPhone (også i Dynamic Island) og Live Update på Android.

### Som valg i reglene du har

Slå på **Vis som Live Activity** under Konfigurer. Valget er av som standard; en regel uten det oppfører seg som før.

- **Støvsuger** – status og rom, med fremdriftslinje hvis du velger en sensor. Knappevarselet beholdes, men kommer stille.
- **Alarm** – nedtelling for utgangs- og inngangstid, deretter «utløst». Krever en `alarm_control_panel`.
- **Ruter** – nedtelling til trikken går, i stedet for et banner som straks er utdatert.
- **Autolås** – nedtelling til døra låses. Trenger en telefon i oppsettet og en ventetid på minst 60 sekunder.
- **Dørlås fastkjørt** – teller opp til låsen er i orden igjen.
- **Egendefinert tilstand** – meldingen din, med valgfri fremdrift og nedtelling, til tilstanden er borte.

### Seks nye typer

- **Elbillading** – batteri mot ladegrense og tid igjen.
- **Hvitevare** – gjenstående tid, fremdrift og programfase.
- **Åpen dør, port eller vindu** – hvor lenge den har stått åpen, med lav prioritet.
- **Timer** – en `timer`-entitet som nedtelling.
- **Basseng** – pumpe som går, med gjenstående tid eller fast kjøretid, og vanntemperatur.
- **Egen fremdrift** – velg selv entitet, fremdrift, tekst og ikon.

### Felles

- Farge, side som åpnes ved trykk, prioritet mot andre aktiviteter, minste tid mellom oppdateringer og hvor lenge «ferdig» blir stående.
- Likt innhold sendes aldri to ganger, og innenfor 30 sekunder sendes bare den siste endringen – iOS struper og dropper ellers oppdateringene.
- Nedtellinger går på telefonen. En sensor som teller ned minutt for minutt gir ingen sendinger.
- Aktiviteten fjernes like før iOS sin åttetimersgrense, og finner tilbake etter omstart uten ny lyd.
- **Test Live Activity**-knapp som viser et eksempel i ett minutt.
- Statusentiteten viser om en aktivitet står på telefonen, og antall sendinger.

## Krav

iOS 17.2 eller Android 16, og Home Assistant 2026.7 eller nyere for iPhone. Eldre telefoner får et vanlig varsel som byttes ut.

## Verdt å vite

- iPhone skjuler meldingen mens en nedtelling vises, og tittelen kan ikke endres etter start. Tittelen er navnet på oppsettet.
- Mange start og stopp under testing kan gjøre at nye aktiviteter uteblir en stund uten feilmelding. Det går over av seg selv.

## Også rettet

- `strings.json` manglet tekstene for tittel og prompt i værmeldingen.

### Kontrollert

Python 3.13.16, Home Assistant 2025.12.5, uten pytest.

- `python -m unittest discover -s tests` – 149 tester bestått, 50 av dem nye. Én hoppet over (publiseringsskriptet, fordi rsync mangler i testmiljøet).
- `python tests/smoke_setup.py` – alle oppsett, også den nye hvitevaren, lastes og avlastes.

Ikke verifisert på en fysisk telefon: utseendet på iPhone og Android, klokke som teller opp, og om «ferdig» gir lyd. Se TESTING.md.
