# KI Varslinger og sikkerhet 2.8.0

## Android: ikon med farge

- Ikonet i statuslinja og i varselet får farge. Standard følger typen (grønn for familie, rød for alarm og fastkjørt lås, oransje for dørvarsel), og alarmvarslene bytter farge etter hendelse.
- Nytt valg **Android – farge på ikonet** og **Android – stort ikon** (et bilde, f.eks. `/local/ikoner/alarm.png`) på alle varslingsoppsett.
- iPhone er uendret.

## Live Updates på Android og Samsung

Live Activities fra 2.7.0 er tilpasset Android 16 – på Samsung One UI 8 med Now Bar og brikke i statuslinja.

- **Kort brikketekst:** inntil sju tegn, så Android viser teksten og ikke bare ikonet. Finnes det ingen tekst, vises prosenten.
- **Festet varsel:** kan ikke sveipes bort mens det pågår, og fjernes av seg selv. Kan slås av per oppsett.
- **Ingen minustid:** Android teller videre under null. Klokka tas nå bort når nedtellingen er ute, og Ruter viser «Har gått nå».
- Eldre Android viser det samme som et festet varsel med fremdriftslinje og klokke.

**Samsung:** slå på **Live-varsler for alle apper** under Utvikleralternativer, ellers vises ikke brikken i statuslinja.

## Oppgradering

Ingen oppsett må endres. Eksisterende Android-varsler får farge på ikonet, og Live Activities blir festet på Android som standard.

### Kontrollert

Python 3.13.16, Home Assistant 2025.12.5, uten pytest.

- `python -m unittest discover -s tests` – 160 tester bestått, 11 av dem nye. Én hoppet over (publiseringsskriptet, fordi rsync mangler i testmiljøet).
- `python tests/smoke_setup.py` – alle oppsett lastes og avlastes.

Ikke verifisert på en Samsung eller annen Android-telefon. Se TESTING.md.
