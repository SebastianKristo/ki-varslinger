# KI Varslinger 1.0.1

Første repo-utgave for installasjon gjennom HACS som egendefinert integrasjon.

- Samler familievarsler, Roborock med varselknapper, alarmvarsler, Ruter og egne tilstandsvarsler.
- Oppsett i Home Assistant-grensesnittet, testknapper og varslingsstatus.
- Separate alarmvarsler for aktivering, deaktivering og utløst alarm.
- HACS-metadata, lokale ikoner, dokumentasjon og lenke til feilrapportering.
- GitHub Actions for HACS, hassfest og lokale HA-tester.
- Mac-skript for commit, tag og release uten force-push.
- Beholder integrasjonsdomenet ki_notifications og lagrede oppsett fra 1.0.0.

Krever Home Assistant 2025.12.5 eller nyere. Installer fra HACS som egendefinert repo og start Home Assistant på nytt. WAV-lydene importeres separat i Companion-appen på iPhone.

Funksjonstester bruker simulerte telefon-/støvsugerhandlinger. Telefonlevering og fysisk utstyr må kontrolleres etter installasjon. Se LES_MEG.md og TESTING.md.
