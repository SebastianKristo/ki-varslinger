# Testresultat – KI Varslinger og sikkerhet 2.0.1

Testet 15. september 2026 med Python 3.13.15 og Home Assistant Core 2025.12.5 i et isolert lokalt miljø.

## Funksjonstester

53 tester bestått. Testene bruker Home Assistants egne State-, Event-, Store- og tjenesteregisterklasser. Notify- og vacuum-handlingene er simulerte og kontakter ingen telefon eller robot.

Dekker: skjemaer, opprettelse av konfigurasjonsoppføring, validering av mottakere, fjerning av valgfrie kilder, opprettelse av plattformentiteter, faktiske tilstandslyttere og avregistrering, familieordlyd/lyd, uavhengige brytere, lagring, sonefilter, alarmforløp, kritisk alarm kontra test, Homey-alarm, uavhengig sending ved mottakerfeil, samme støvsugervarsel med Pause → Start, umiddelbar Start før robotens tilstand har oppdatert seg, avvisning av gamle knapper, sikre støvsugertester og gyldige transportavganger.

Fra pakkens rot, i et Python-miljø med Home Assistant installert:

```sh
python -m unittest discover -s tests -v
```

## Innlastingstest

`python tests/smoke_setup.py` passerer også:

- HAs integrasjonslaster finner den egendefinerte integrasjonen.
- En familieoppføring når `ConfigEntryState.LOADED`.
- Sju brytere (inkludert hovedbryteren), to knapper og én statusentitet opprettes i entitetsregisteret.
- En posisjonsendring kaller den simulerte notify-handlingen med korrekt tekst.
- HAs Options Flow åpner innstillingsskjemaet.
- Integrasjonen avlastes uten feil.

Denne testen markerer Companion som tilgjengelig, bruker en simulert notify-handling og slår av automatisk pakkeinstallasjon i testmiljøet. Den erstatter ikke en test av mobilappen eller en full HAOS-installasjon. HAs standardadvarsel om uoffisielle custom integrations vises som forventet.

## Ikke verifisert på fysisk utstyr

Telefonlevering, lydnivå, iOS/Android-visning og utskifting av varsler, fysisk Roborock, Homey-tilkobling, alarmutstyr og kalender-/transportsensorene dine. Ruter-kalendervinduet er implementert, men ikke kjørt mot en ekte kalender. Utfør de innebygde testene og én ordinær hendelse per oppsett etter installasjon. Integrasjonen tester aldri alarmen ved å utløse den.

## HACS og publiseringsskript (1.0.1)

Begge manifestene passerer JSON-skjemaene fra HACS-kildekoden hentet 12. september 2026. Lokale brand-ikoner følger med. Bash-syntaks er kontrollert.

Publiseringsskriptet er kjørt mot et midlertidig Git-repo med simulert GitHub CLI. Testen kontrollerer commit/tag/push, release-kallet, bevaring av uvedkommende filer og stopp ved eksisterende tag eller lokale endringer. Ingen kode er publisert til GitHub av testen. Skriptet bruker Bash 3.2-kompatibel syntaks, men er kjørt på Linux i testmiljøet, ikke på en fysisk Mac.

HACS- og hassfest-jobbene på GitHub kan først bekreftes etter opplasting. Full HACS-installasjon er ikke testet i brukerens Home Assistant.

## Nye varseltyper i 1.1.0

Ni nye tester kontrollerer lokal 08:00-planlegging, ukedager og hjemmebetingelse, lagret dagsgrense, AI-tekst og vindens måleenhet, valgt AI-entitet, reservevarsel ved manglende AI-/værhandling, 60 sekunders jammed-timer, avbrutt og ny fastkjøring, attributtendringer uten nullstilling, deaktivering, oppstartsvarsel kontra reload samt avbrutt oppstartsforsinkelse ved avlasting. Tidsutløserne er simulert i testene; det er ikke ventet en hel morgen eller restartet fysisk utstyr.

AI Task og weather.get_forecasts er simulert med HAs tjenesteregister og responsstøtte. Ingen eksterne AI-kall eller push-varsler er sendt under testingen.

## Hovedbryter i 1.2.0

Fire nye tester kontrollerer at hovedbryteren blokkerer automatiske familie- og alarmvarsler, bevarer individuelle valg, tillater eksplisitte testvarsler, lagres/gjenopprettes og bare opprettes for oppsett med flere brytere. Eldre lagringsformat uten hovedbryter migreres med hovedbryteren på. Innlastingstesten bekrefter nå ti familieentiteter.

## Sikkerhetsfunksjoner i 2.0.1

18 nye tester med simulerte enheter dekker: sikkerhetsfunksjoner av som standard og uten fysiske testhandlinger; autolåstimer, kontroll av lukket dør og ulåst lås, avbrudd ved åpning/ukjent sensor/avslått funksjon; tallfelt og ekstern input_number med lagring; toveis armering/deaktivering, korrekt privacy mode etter bekreftelse, beskyttelse mot ekko som ellers ville byttet hjemmemodus til bortemodus; feil ved armering, bekreftelsestidsavbrudd og motstridende alarmtilstander; tre lokale webhooks med metodevalg og opprydding; avvisning av ekstern kilde gjennom HAs webhook-handler; personregistrering først etter bekreftet opplåsing, lagring og korrekt navn for hvert av de tre endepunktene; ingen ny person ved allerede ulåst dør, feil eller tidsavbrudd.

Innlastingstesten oppretter også autolås og ansiktsgjenkjenning i HAs virkelige konfigurasjons- og entitetsregister: begge får tre entiteter og starter avslått. Webhookene avregistreres ved avlasting. Companion- og webhook-transport regnes som oppsatt i denne testen, og nettverkskall til fysisk utstyr er ikke utført.

HTTP-testene bruker simulerte lokale/eksterne forespørsler, ikke det virkelige kameraet. Alarmo/Homey, Bluetooth-låsen, dørkontaktens rå verdier og mekanisk låsing må testes hos brukeren. Ingen ekte PIN-kode eller brukerens webhook-ID-er inngår i testene.

## Autolåsretting 2.0.1

Nye regresjonstester kontrollerer at endret ventetid i innstillinger overstyrer tidligere lagring, at tallendringer fortsatt huskes, at feil rå dørverdier forklares uten låsekommando, at eksplisitt on/off-oppsett låser etter nedtelling, og at rene attributtoppdateringer ikke starter nedtellingen på nytt. Statusattributter inneholder ingen låsekode. Full funksjonstest og innlastingstest besto 15. september 2026.
