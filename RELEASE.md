# KI Varslinger og sikkerhet 2.6.1

## CI er grønn igjen

Validate-jobben var rød — ikke fordi en test feilet, men fordi én testfil ikke kunne lastes.
`tests/test_vaerprompt.py` begynte med `import pytest`, og CI kjører `python -m unittest` i et miljø
der pytest ikke er installert. Da feilet importen, og hele testjobben ble rød — mens de 90 andre
testene, også de 16 nye for dørvarselet, gikk grønt i samme kjøring.

Feilen kom inn med 2.5.0, så den kjøringen var rød også. Den ble ikke oppdaget fordi pytest fantes
på maskinene testene ble kjørt på lokalt.

Filen er skrevet om til `unittest` med de samme sjekkene (`subTest` i stedet for `parametrize`), og
henter nå standardtekstene fra `const.py` i stedet for en kopi. En ny test passer på at de tre
linjene den etterligner, fortsatt står i `extra_notifications.py`, så den ikke tester noe som ikke
finnes lenger.

## Innlastingstesten dekker dørvarselet

`tests/smoke_setup.py` — som laster integrasjonen gjennom Home Assistants egen laster — setter nå også
opp en «Dør – låst/åpnet med kamerabilde»: den når `LOADED`, får sju entiteter (fire hendelsesbrytere,
hovedbryter, testknapp og status), starter med «lukket» av og de tre andre på, og avlastes rent.

### Kontrollert

Kjørt i **samme miljø som CI**: Python 3.13.15, Home Assistant 2025.12.5, uten pytest.

- `python -m unittest discover -s tests` — 99 tester, alle bestått, ingen hoppet over
- `python tests/smoke_setup.py` — familie, dørlys, autolås, ansiktsgjenkjenning og dørvarsel lastes
  og avlastes

Ingen endring i integrasjonens oppførsel fra 2.6.0.
