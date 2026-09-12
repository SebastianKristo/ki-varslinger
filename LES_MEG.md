# KI Varslinger 1.0.1

En egendefinert Home Assistant-integrasjon for familie, støvsuger, alarm, egne tilstandsendringer og Ruter-varsler. Oppsett og endringer gjøres i brukergrensesnittet. Ingen YAML-pakke eller KI-testskript kreves.

## Installer

1. Pakk ut ZIP-filen på datamaskinen.
2. Kopier mappen `custom_components/ki_notifications` til `/config/custom_components/ki_notifications` i Home Assistant. Filen `/config/custom_components/ki_notifications/manifest.json` skal ligge direkte der, uten en ekstra undermappe.
3. Start Home Assistant på nytt.
4. Gå til **Innstillinger → Enheter og tjenester → Legg til integrasjon**. Søk etter **KI Varslinger**. Oppdater nettlesersiden hvis den ikke vises.
5. Velg typen varsling og fullfør skjemaet. Legg til integrasjonen igjen for hver ekstra type eller regel.
6. Åpne enheten integrasjonen oppretter. Her finner du av/på-brytere, testknapper og **Varslingsstatus**. Legg ønskede entiteter på dashbordet med **Legg til på dashbord**.
7. Bruk **Konfigurer/Alternativer** på integrasjonsoppføringen for å endre mottakere, kilder, lyd og øvrige innstillinger.

Home Assistant Companion må allerede være registrert på telefonene, og de direkte notify-handlingene må fungere. Det gjør de hos deg. Telefonene foreslås automatisk hvis handlingene finnes:

- iPhone: `mobile_app_sebastian_iphone_17_pro`
- Pixel: `mobile_app_sebastian_pixel_9_pro_fold`

Velg handlingene uten `notify.` foran. Du kan velge flere mottakere, men samme mottaker skal ikke velges både som iPhone og Android.

Pakken kan installeres manuelt eller fra HACS som et egendefinert repo etter at koden og releasen er publisert. Den er ikke automatisk oppført i HACS-standardkatalogen. Den trenger ingen API-nøkkel. Reglene kjører lokalt; levering til telefonene bruker Home Assistant Companion sin vanlige varsling.

## Flytt fra tidligere automasjoner

Deaktiver den gamle familieautomasjonen, Roborock-varslene og Ruter-varslingen når det tilsvarende nye oppsettet er testet. Ellers kan du få dobbeltvarsler. Ingen gamle filer eller automasjoner slettes automatisk.

Familieoppsettet leser de gamle seks `input_boolean.posisjonsvarsel_*`-bryterne ved første oppstart hvis de finnes og har gyldig tilstand. Deretter bruker det egne brytere med lagrede valg. Hvis gamle brytere ikke er tilgjengelige første gang, starter de nye på. Kontroller valgene på integrasjonens enhet. Gamle dashbordbrytere må erstattes med de nye; entitets-ID-ene er ikke de samme.

Lyder velges i det nye oppsettet; de gamle `input_select`-lydvelgerne styrer ikke integrasjonen. Start gjerne med `default` for første test.

## Familie – Rune, Cybele og Sebastian

Velg hjemme/borte-bryteren til hver person. De kjente Homey-bryterne foreslås hvis de finnes:

- `switch.rune_posisjon_hjemme_borte`
- `switch.cybele_posisjon_hjemme_borte`
- `switch.sebastian_posisjon_hjemme_borte`

`off → on` sender «Rune kom hjem.». `on → off` sender «Rune forlot huset.». Tilsvarende for Cybele og Sebastian. Integrasjonen endrer aldri posisjonsbryterne.

Seks separate av/på-brytere styrer ankomst og avreise uavhengig for hver person. Valgene lagres ved endring og gjenopprettes ved omstart. Testknappene omgår disse bryterne og sender «Test kom hjem.» eller «Test forlot huset.».

Det sendes ikke ankomst-/avreisevarsler bare fordi en entitet blir tilgjengelig etter `unknown` eller `unavailable`. Hver faktisk ankomst/avreise er et eget varsel.

## Støvsuger – Sir Sweeps A Lot

Velg `vacuum.sir_sweeps_a_lot`, romsensoren `sensor.sir_sweeps_a_lot_current_room` og eventuelt romvalgbryterne dine. Integrasjonen styrer støvsugeren med de vanlige `vacuum`-handlingene.

- Ved start sendes ett varsel. Status og rom oppdateres med samme varsel-ID.
- Under rengjøring: **Pause**, **Stopp**, **Hjem**.
- Ved pause/stopp: **Start**, **Stopp**, **Hjem**.
- Ved retur: **Stopp**.
- Pause-knappen byttes til Start straks Home Assistant har godtatt kommandoen. Faktisk rapportert støvsugertilstand oppdaterer visningen etterpå; etter 10 sekunder leses den også på nytt hvis ingen tilstandsendring kom.
- Varslet viser nåværende rom og valgte rom. Valgte rom er merket som valg, ikke som en bekreftet rengjøringsplan.
- Ved lading eller feil oppdateres varslet med sluttstatus uten kontrollknapper. Det beholdes til det fjernes eller erstattes av neste økt.
- Slår du av støvsugervarslingen, sendes en kommando om å fjerne varslet.

Knappene gjelder den konfigurerte støvsugeren. Gamle kontrollknapper ugyldiggjøres etter en godtatt kommando, ved avsluttet økt og ved omstart. Ved omstart mens støvsugeren går, gjenopptas overvåkingen; nytt varsel sendes ved neste status-/romendring. Testknappen sender bare et demonstrasjonsvarsel, uten kontrollknapper eller start av roboten.

Bruk lange trykk/utvid varselet på iPhone for å se knappene. OS-et avgjør hvor fort en oppdatering vises og om varslet beholdes etter knappetrykk. Dette er et vanlig Companion-varsel som erstattes via `tag`, ikke en iOS Live Activity. Romoppdateringene ber om stille levering; Android har en egen kanal for stille oppdateringer. Integrasjonen kan ikke garantere telefonens presentasjon eller at en allerede fjernet melding gjenopprettes.

## Alarm

Legg til et oppsett av typen **Alarm**. Du kan legge til flere alarmer som separate oppsett.

**Vanlig HA-alarm:** Velg en `alarm_control_panel`-entitet. Integrasjonen varsler når den blir aktivert (`armed_*`), deaktivert (`disarmed`) eller utløst (`triggered`). Overgang til `arming` er ikke fullført aktivering. Bytte mellom to aktive moduser og retur fra `triggered`/`pending` til aktiv alarm gir ikke en ekstra aktiveringsmelding.

**Homey-alarm:** Velg en `switch` eller `input_boolean` der `on` betyr aktivert og `off` betyr deaktivert. Velg i tillegg en egen bryter/binærsensor for utløst alarm dersom Homey eksponerer dette. Denne varsler på `off → on`. En aktiveringsbryter alene kan ikke fortelle at alarmen er utløst.

Du får tre uavhengige varselbrytere og tre testknapper:

| Hendelse | Melding |
| --- | --- |
| Aktivering | 🔒 Alarm aktivert. |
| Deaktivering | 🔓 Alarm deaktivert. |
| Utløst alarm | 🚨 Alarm utløst. |

Ikonet står i tittelen; meldingsteksten er uten emoji. Testmeldingene er tydelig merket TEST og endrer aldri alarmens tilstand. Varsling startes ved nye gyldige tilstandsendringer, ikke ved oppstart eller gjenoppkobling.

**Kritisk iPhone-varsel** er et valgfritt avkrysningsfelt som er av som standard. Hvis du slår det på og gir Companion tillatelse til kritiske varsler i iOS, ber en faktisk utløst alarm om kritisk lyd med full volumverdi. Vanlig aktivering/deaktivering og testknappene er ikke kritiske. Android styres fortsatt av telefonens varselkanal og Ikke forstyrr-innstillinger. Det er ingen knapper for å aktivere eller deaktivere selve alarmen.

## Egendefinerte tilstandsvarsler

Legg til ett oppsett per regel. Velg entitet, eksakt fra- og tiltilstand, melding og ikon. Det kan brukes til dør, bevegelse, ekstra personer med on/off-brytere, Homey-hendelser og andre sensorer.

Meldingen er vanlig tekst. Tilstander er de interne HA-verdiene, for eksempel `off`, `on`, `home` eller `not_home`, ikke nødvendigvis oversettelsen i dashbordet.

Et valgfritt sonefilter krever både person/telefon og én eller flere soner. Varslet sendes bare hvis personen er i minst én valgt sone når tilstandsendringen skjer. Testknappen omgår filteret. Sonen bestemmes fra koordinater når de finnes, ellers fra personens sonenavn. Rene attributtendringer utløser ikke denne regeltypen.

## Ruter – fra skolen

Velg telefoner/personer, skolesoner, timeplankalender og transportsensorene dine. De kjente entitetene foreslås når de finnes.

Varslingen skjer ved:

- Avreise fra alle de valgte skolesonene: den gamle posisjonen må ha vært innenfor minst én av dem. Da trenger ikke den nye posisjonen fortsatt være på skolen.
- Valgt antall minutter før den aktive kalenderhendelsen slutter, forutsatt at minst én telefon/person fortsatt er i en skolesone.

Nære doble avreisemeldinger fra to telefoner begrenses med 90 sekunders pause. Testknappen omgår dette og sonefilteret.

Transportformatet følger sensorene fra din tidligere Ruter-automasjon: tilstanden er antall minutter til avgang, og attributtene er `route`, `due_at`, `next_route`, `next_due_in`, `next_due_at`. Andre dataformater må først normaliseres i HA. Busssensorene du velger må allerede gjelde riktig linje/retning.

Trikk filtreres etter retningsord og tidligste avgang som rekker gangtiden. Buss velges etter trikkens avgangstid + reisetid + overgangstid. Gangtiden legges ikke til to ganger. Manglende/rutemessig uoppnåelige avganger vises som manglende, ikke som en oppdiktet avgang. T-banen vises separat uten å love at overgangen rekkes.

Kalenderen kontrolleres hvert 30. sekund og bruker kalenderentitetens aktive hendelse. Overlappende hendelser, heldagshendelser og historikk etter nedetid håndteres ikke som en full kalenderkø. Ingen avganger hentes direkte fra Ruter/Entur av denne integrasjonen; de eksisterende transportsensorene leverer dataene.

## Egendefinerte lyder

Mappen `sounds` inneholder `kom_hjem.wav` og `forlot_huset.wav`: de to myke varsellydene vi laget, stigende ved ankomst og fallende ved avreise. De er ikke kopier av Homey-lyden.

1. Lagre WAV-filene i **Filer** på iPhone.
2. I Companion-appen: **Innstillinger → Companion App → Varslinger → Lyder → Importer egendefinert lyd**.
3. Importer begge og start iPhone på nytt.
4. I integrasjonens Alternativer: sett iPhone-lyd til `kom_hjem.wav` og lyd ved avreise til `forlot_huset.wav`.
5. Test fra integrasjonens enhet.

Filene er mono WAV, 32-bit float, 48 kHz, 1,35 sekunder. Lydfilene skal importeres på hver mottakende iPhone; å legge dem under `/config` gjør ikke dette. Vanlige varsler følger stillemodus, volum og iOS-tillatelser.

På Pixel velger du lyd i Android-innstillingene for Home Assistants varselkanaler. Bruk gjerne egne kanalnavn per oppsett, som `KI Familie`, `KI Alarm` og `KI Roborock`. Android husker kanalinnstillinger; endring av YAML eller kode endrer ikke en tidligere valgt lyd på telefonen. Hold kanalen «stille oppdateringer» stille.

## Feilsøking og kontroll

Åpne **Varslingsstatus** på integrasjonens enhet. Attributtene viser siste melding, tidspunktet da minst én notify-handling lyktes, og siste sendefeil. «Sendt» betyr at Home Assistant-handlingen lyktes, ikke at telefonen bekreftet levering. Feil på én mottaker stopper ikke forsøket til den andre. Feilen logges også under KI Varslinger i HA-loggen.

Hvis test virker, men ordinære varsler mangler: kontroller den nye varselbryteren, faktisk tilstandsendring på kilden og eventuelt sonefilter. Har en entitet fått nytt ID, velg den på nytt i Alternativer. Endringer lastes inn uten full omstart.

Ved avinstallering: fjern integrasjonsoppføringene, fjern mappen `custom_components/ki_notifications`, og start HA på nytt. Egne lagrede brytervalg slettes når oppføringen fjernes. De gamle automasjonene kan aktiveres igjen om ønskelig.

## Testgrunnlag og omfang

Kildekode, UI-skjemaer og hendelseshåndtering er testet lokalt med Home Assistant 2025.12.5. Testene bruker HAs ekte tilstandsmaskin og tjenesteregister med simulerte notify-/vacuum-handlinger. De sender ikke til telefoner og kjører ikke en fysisk alarm. Se `TESTING.md` for resultat og kjørekommando.

Installasjon i din HA-instans, nettleservisning, fysisk Roborock og iPhone/Pixel-lyd er ikke testet her. Dette er første versjon. Lysstyringen på soverommet, klimastyringen og nattmodus-kortet er separate funksjoner; denne integrasjonen samler varslingen.
