# KI Varslinger

[![Validate](https://github.com/SebastianKristo/ki-varslinger/actions/workflows/validate.yml/badge.svg)](https://github.com/SebastianKristo/ki-varslinger/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/SebastianKristo/ki-varslinger)](https://github.com/SebastianKristo/ki-varslinger/releases)

![KI Varslinger](custom_components/ki_notifications/brand/icon.png)

Varslingsintegrasjon for Home Assistant med oppsett i brukergrensesnittet, iPhone/Android-mottakere, testknapper og status ved sendefeil.

| Oppsett | Funksjoner |
| --- | --- |
| Familie | Rune, Cybele og Sebastian. Egne brytere for kom hjem / forlot huset per person. |
| Roborock | Oppdatering av samme varsel, romvisning, Pause/Start, Stopp og Hjem. |
| Alarm | Aktivering, deaktivering og utløst alarm. Alarmenheter eller Homey-brytere. |
| Værmelding – AI | Kl. 08 hver dag når Sebastian er hjemme; daglig prognose og AI-sammendrag. |
| HA startet | Dato og klokkeslett ved faktisk HA-oppstart, med valgfri forsinkelse. |
| Dørlås fastkjørt | Varsler etter ett sammenhengende minutt i jammed. |
| Egne varsler | Valgfri entitet, fra-/tiltilstand, tekst, ikon og sonefilter. |
| Ruter | Skolefilter, kalenderpåminnelse og avganger fra eksisterende transportsensorer. |

To egendefinerte varsellyder følger med i [sounds](sounds). De importeres separat på iPhone.

## Installer med HACS

Krever Home Assistant **2025.12.5 eller nyere**, HACS og Home Assistant Companion på mottakertelefonene.

1. Åpne **HACS → menyen ⋮ → Egendefinerte repositorier / Custom repositories**.
2. Legg til `https://github.com/SebastianKristo/ki-varslinger` med type **Integrasjon / Integration**.
3. Finn **KI Varslinger**, velg og last ned siste release.
4. Start Home Assistant på nytt.
5. Velg **Innstillinger → Enheter og tjenester → Legg til integrasjon → KI Varslinger**.
6. Legg til ett oppsett per ønsket varseltype. Testknapper og brytere finnes på den tilhørende enheten.

Repoet må ha fått kode og release før det kan installeres på denne måten. Dette er støtte for et egendefinert HACS-repo, ikke godkjenning i HACS-standardkatalogen. HACS installerer integrasjonsmappen fra versjonstaggen; den vedlagte ZIP-en er en komplett kildekodepakke for terminalopplasting og manuell bruk.

**Oppgradering fra manuell installasjon:** domenet er fortsatt `ki_notifications`. Eksisterende oppsett og brytervalg beholdes når HACS overtar den samme integrasjonsmappen. Integrasjonen heter nå KI Varslinger i grensesnittet.

## Bruk og migrering

Se [LES_MEG.md](LES_MEG.md) for alarmoppsett, lydimport, Ruter-format, begrensninger og feilsøking. Deaktiver tilsvarende gamle automasjoner etter testing for å unngå dobbeltvarsler.

Støvsugeren bruker vanlige Companion-varsler med samme `tag`, ikke iOS Live Activities. Telefonens OS bestemmer presentasjon og lyd. Alarmtestene endrer ikke alarmtilstand; kritisk iPhone-varsling er et eget, valgfritt valg for faktisk utløst alarm.

## Publiser fra Mac

Last ned `ki-varslinger-1.1.0.zip` til `~/Downloads`. Kjør:

```bash
mkdir -p "$HOME/Downloads/ki-varslinger-1.1.0"
ditto -x -k "$HOME/Downloads/ki-varslinger-1.1.0.zip" "$HOME/Downloads/ki-varslinger-1.1.0"
bash "$HOME/Downloads/ki-varslinger-1.1.0/ki-varslinger/scripts/publish-macos.sh" 1.1.0
```

Skriptet bruker `~/Documents/HomeAssistant/ki-varslinger`, eksisterende GitHub CLI-innlogging og grenen `main`. Det oppdaterer repoets beskrivelse, topics og Issues, pusher commit/tag og publiserer en release med [RELEASE.md](RELEASE.md) og ZIP-en. Trenger du avhengighetene: `brew install git gh python rsync`.

Lokale endringer og eksisterende versjonstagger stopper skriptet. Det overskriver ikke tagger og bruker ikke force-push. Nye versjoner må få nytt nummer i manifest, enhetens `sw_version`, releasenotat og pakkenavn. Bruk samme versjon som argument.

Hvis push feiler etter at lokal commit/tag er opprettet, ligger arbeidet igjen lokalt. Løs den rapporterte feilen og kjør fra repoet, for eksempel for 1.1.0:

```bash
cd "$HOME/Documents/HomeAssistant/ki-varslinger"
git push --atomic origin main refs/tags/v1.1.0
```

Hvis kun release-opprettelsen feiler etter vellykket push, kan den fullføres uten ny commit/tag:

```bash
cd "$HOME/Documents/HomeAssistant/ki-varslinger"
gh release create v1.1.0 "$HOME/Downloads/ki-varslinger-1.1.0.zip" \
  --repo SebastianKristo/ki-varslinger --verify-tag \
  --title "KI Varslinger 1.1.0" --notes-file RELEASE.md
```

Sjekk om releasen allerede finnes før du kjører gjenopprettingskommandoen. Ved manglende Git-identitet må `git config user.name` og `git config user.email` settes til dine egne verdier.

## Validering

GitHub Actions kjører HACS-validering, Home Assistants hassfest, funksjonstester og innlastingstest på push, tag og pull request. Se [TESTING.md](TESTING.md) for lokale resultater og forskjellen mellom simulerte tester og fysisk utstyr. GitHub-kontrollene må få kjøre etter opplasting; en lokal kontroll er ikke et grønt resultat fra GitHub.

## Lisens

[Apache License 2.0](LICENSE), beholdt fra dette repoet.
