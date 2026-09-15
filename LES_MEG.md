# KI Varslinger og sikkerhet 2.2.0

En egendefinert Home Assistant-integrasjon for familie, støvsuger, alarm, egne tilstandsendringer og Ruter-varsler. Oppsett og endringer gjøres i brukergrensesnittet. Ingen YAML-pakke eller KI-testskript kreves.

## Installer

1. Pakk ut ZIP-filen på datamaskinen.
2. Kopier mappen `custom_components/ki_notifications` til `/config/custom_components/ki_notifications` i Home Assistant. Filen `/config/custom_components/ki_notifications/manifest.json` skal ligge direkte der, uten en ekstra undermappe.
3. Start Home Assistant på nytt.
4. Gå til **Innstillinger → Enheter og tjenester → Legg til integrasjon**. Søk etter **KI Varslinger og sikkerhet**. Oppdater nettlesersiden hvis den ikke vises.
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

## Sikkerhetsfunksjoner – nytt i 2.2.0

Navnet er endret til **KI Varslinger og sikkerhet** i HA/HACS. Domenet `ki_notifications`, repoet `SebastianKristo/ki-varslinger` og gamle varslingsoppsett beholdes. De tre sikkerhetsfunksjonene legges til som egne oppsett og starter **avslått**. Autolås har en uttrykkelig merket testknapp som kan låse etter ventetiden. Alarmsynk og ansiktsgjenkjenning har ingen testknapp som betjener lås eller alarm.

Sikkerhetsoppsettene krever ikke en telefonmottaker. De styrer enhetene og har en statusentitet. Ønsker du push-varsler om alarmtilstand eller fastkjørt lås, bruker du de egne varslingsoppsettene som allerede finnes i integrasjonen.

### Autolås

1. Legg til typen **Autolås**.
2. Velg låsen, normalt `lock.dorlas_blatann`.
3. Velg dørsensoren `sensor.inngangsdor`.
4. Fyll inn sensorens faktiske tilstander for **åpen** og **lukket**. Standard er `open`/`closed`; for en binærsensor brukes ofte `on`/`off`. Dersom din sensor har tekstverdier som `Åpen` og `Lukket`, skriv disse nøyaktig. Kontroller rå tilstand i Utviklerverktøy → Tilstander.
5. Velg standard ventetid. Integrasjonen oppretter tallfeltet **Ventetid før autolås**, som kan legges på dashbordet. Feltet er en integrasjonseid `number`-entitet, med område 5–3600 sekunder, og husker verdien ved omstart.
6. Vil du bruke en ekte `input_number`-helper, opprett den under **Innstillinger → Enheter og tjenester → Hjelpere → Tall**, og velg den i **Bruk eksisterende input_number for ventetid**. Da brukes helperen og det opprettes ikke et ekstra number-felt. Helperen må ha en gyldig verdi mellom 5 og 3600 sekunder.
7. Fyll eventuelt inn koden låsen krever og slå på bryteren **Autolås**.

Nedtellingen starter ved en faktisk overgang fra konfigurert åpen til lukket. Åpning, ukjent eller utilgjengelig dørsensor avbryter. Når tiden er ute, sjekkes at døren fremdeles er lukket og at låsen er bekreftet ulåst før `lock.lock` kalles. Er låsen allerede låst, gjøres ingenting. Andre låstilstander gir statusfeil og ingen låsekommando.

Endring av ventetiden under en nedtelling regnes fra den opprinnelige lukkingen. Gjør du ventetiden kortere enn tiden som allerede har gått, kan låsekommandoen derfor komme straks. Ved omstart, reload eller etter at funksjonen har vært avslått, starter det ikke en ny nedtelling fra et gammelt lukket øyeblikksbilde; døren må åpnes og lukkes på nytt. Opplåsing av en dør som allerede står lukket starter heller ikke en ny nedtelling.

Autolåsen er avhengig av at dørsensoren rapporterer korrekt. Tiden og tilstandene må prøves på din fysiske dør; en simulert test kan ikke bekrefte at låsereilen og døren fungerer mekanisk sammen.

### Heimdall i Homey ↔ Alarmo

Velg **Heimdall ↔ Alarmo** med:

- Alarmo: `alarm_control_panel.alarm`.
- Heimdall: `select.alarm_homealarm_state`.
- Heimdall-valg for aktivert/deaktivert: `armed` / `disarmed`.
- Alarmo-modus ved aktivering fra Heimdall: normalt `armed_away`, som i din gamle automasjon.
- Alarmkode: fylles inn i passordfeltet i HA.
- Kameraenes privacy mode-brytere: `switch.mellomgang_g5_turret_ultra_privacy_mode` og `switch.stue_g6_turret_privacy_mode` foreslås når de finnes.

Etter at bryteren er slått på, brukes nye tilstandsendringer:

| Endring | Handling |
| --- | --- |
| Heimdall blir `armed` | Aktiverer valgt Alarmo-modus dersom Alarmo ikke allerede er aktivert. |
| Heimdall blir `disarmed` | Deaktiverer Alarmo. |
| Alarmo blir `armed_away`, `armed_home`, `armed_night`, `armed_vacation` eller annen `armed_*`-tilstand | Setter Heimdall til `armed`. |
| Alarmo blir `disarmed` | Setter Heimdall til `disarmed`. |
| Alarmo bekrefter aktivert | Slår av privacy mode på valgte kameraer. |
| Alarmo bekrefter deaktivert | Slår på privacy mode på valgte kameraer. |

Heimdall-selecten din viser to nivåer (`armed`/`disarmed`). Derfor kan ikke alle Alarmo-moduser representeres én til én i den. En endring fra Alarmo natt-/hjemmemodus speiles til `armed`, men ekkoet aktiverer ikke Alarmo på nytt som bortemodus. Utløst alarm, inngangs-/utgangsforsinkelse og andre mellomtilstander kopieres ikke til en oppdiktet Heimdall-verdi. Bruk alarmvarslingsoppsettet for varsler om utløst alarm.

Kameraene endres etter bekreftet Alarmo-tilstand, ikke bare fordi det ble sendt en armeringskommando. Mislykket armering skal dermed ikke automatisk slå av kameraenes privacy mode.

Forventede svar fra det andre systemet gjenkjennes for å unngå returløkker. Manglende bekreftelse etter standard 120 sekunder, utilgjengelig mål eller en motstridende bekreftelse vises i **Sikkerhetsstatus**. Integrasjonen forsøker ikke uendelig på nytt. Kontroller begge systemene ved feil. Ingen synkroniseringskommando sendes bare ved HA-oppstart, reload eller aktivering av bryteren. Hvis systemene er ulike da, sett ønsket tilstand manuelt på ett av dem for å utløse en ny endring.

**Deaktiver den gamle toveis synkroniseringsautomasjonen før den nye funksjonen slås på.** To parallelle synkmotorer kan gi motstridende kommandoer.

### Ansiktsgjenkjenning – dørlås

Selve ansiktsgjenkjenningen skjer fortsatt i kameraet/eksisterende system. Integrasjonen mottar tre ulike webhook-kall og kobler hvert endepunkt til Sebastian, Rune eller Cybele.

1. Legg til **Ansiktsgjenkjenning – dørlås**, og velg `lock.dorlas_blatann`.
2. Skriv låsekoden i feltet **Låse-/alarmkode**.
3. Tre tilfeldige webhook-ID-er foreslås. Du kan erstatte dem med de tre ID-ene fra dine gamle automasjoner. ID-ene skal være ulike og registreres bare lokalt i ditt HA-oppsett.
4. Skal gamle ID-er gjenbrukes, deaktiver de gamle webhook-automasjonene og last automasjonene inn på nytt først, slik at ID-ene blir frigitt. Integrasjonen overskriver ikke andres webhook-registreringer.
5. Sett hvert kamera-/gjenkjenningskall til `http://DIN-HA-ADRESSE:8123/api/webhook/ID_FOR_PERSONEN`, med din faktiske HA-adresse, port og protokoll. ID-en tilhører URL-stien; ikke legg den i et `?`-queryfelt.
6. Bruk **POST** eller **PUT**. Hvis systemet ditt bare sender GET, slå på **Tillat opplåsing med GET**. **HEAD** er kun en kontroll av endepunktet og låser aldri opp, i motsetning til det gamle YAML-eksemplet der alle metodene var utløsere.
7. Slå på funksjonsbryteren når endepunktene er konfigurert.

Webhookene registreres med `local_only: true`. Bruk den lokale HA-adressen. Det er webhook-ID-en og lokalt opphav som gir adgang; integrasjonen validerer ikke selve ansiktsbildet. ID-ene må derfor behandles som adgangsnøkler. De publiseres ikke i repoet eller som sensorattributter. Passordfeltet skjuler dem i skjemaet; HA lagrer konfigurasjonsverdier i `.storage`, så ikke legg HA-konfigurasjon eller sikkerhetskopier i GitHub.

En webhook sender bare opplåsingskommando hvis låsen er bekreftet `locked`. Allerede `unlocked` fører ikke til en ny opplåsing eller en ny personregistrering. Ved ustabil/ukjent låstilstand avvises forsøket. Standard er minst 10 sekunder mellom faktiske forsøk.

Etter kommandoen venter integrasjonen inntil 15 sekunder på `unlocked`. Først da oppdateres sensoren **Sist låst opp av** til **Sebastian**, **Rune** eller **Cybele**, med tidspunkt i attributtet `bekreftet_tid`. Verdien huskes ved omstart. Dette betyr «opplåsing bekreftet etter denne personens webhook»; det er ikke en uavhengig bekreftelse av ansiktsidentiteten. Feil eller manglende bekreftelse registrerer ingen ny person og vises i Sikkerhetsstatus.

Ingen fysisk opplåsing foretas under de medfølgende automatiske testene. Prøv oppsettet på ditt utstyr etter at de gamle automasjonene er deaktivert.

## Hovedbryter for oppsett med flere valg

Familie- og alarmoppsettet får bryteren **Alle varsler**. Den styrer all automatisk varsling i det aktuelle oppsettet, uten å endre de individuelle bryterne. Har du slått av «Rune – kom hjem», forblir dette valget av etter at hovedbryteren slås av og på. Du kan også endre enkeltvalgene mens hovedbryteren er av.

Hovedbryteren og enkeltvalgene huskes etter omstart. Ved oppgradering starter den nye hovedbryteren på, slik at eksisterende varsling fortsetter. Andre oppsett med bare én varselbryter får ikke en ekstra hovedbryter. Bryteren påvirker ikke andre integrasjonsoppføringer.

Bevisst trykk på en **testknapp** sender fortsatt testvarsel når hovedbryteren er av, som ved de øvrige varselbryterne. For alarm gjelder hovedbryteren også automatiske varsler om utløst alarm, inkludert kritiske varsler.

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

## Værmelding – AI

Legg til oppsettet **Værmelding – AI**. Standard er klokken **08:00:00 alle ukedager**, i Home Assistants tidssone, med `weather.forecast_home` og hjemmebryteren `switch.sebastian_posisjon_hjemme_borte`. Tilstanden som betyr hjemme er `on`; ved bruk av en `person` er det vanligvis `home`.

Ved klokkeslettet må hjemmebetingelsen være oppfylt. Det sendes ingen innhenting av et tapt morgenvarsel når du kommer hjem senere. En planlagt sending kjøres maksimalt én gang per lokal dato; dette huskes også ved omstart. Ukedager og tid kan endres i Alternativer.

Integrasjonen kaller `weather.get_forecasts` med `daily`, velger den daterte prognosen for i dag og sender tilgjengelige verdier til `ai_task.generate_data`. Oppgaven ber om 2–3 vennlige setninger på norsk med råd om klær. Måleenhetene leses fra værsensoren; vind antas ikke å være m/s. AI Task må være satt opp i HA, enten som standard AI Task eller som entiteten du velger i oppsettet. Værdataene behandles av din valgte AI-leverandør.

Varslet har tittelen **God morgen ☀️** og værikon. Hvis værprognosen eller AI-tjenesten feiler, brukes tilgjengelige målinger i et enkelt tekstvarsel; feilen vises under **Datakildefeil** i statusentiteten. Manglende data diktes ikke opp. Testknappen omgår tid, hjemmebetingelse og dagsgrense, og kaller også AI-tjenesten når data finnes.

## Home Assistant startet

Legg til **Home Assistant startet**. Ved en faktisk HA-oppstart sendes «Home Assistant ble startet på nytt dd.mm.åååå kl tt:mm:ss.», med Home Assistant-ikon. Tidspunktet er start-hendelsens tidspunkt i HAs tidssone.

Standard ventetid er **15 sekunder** etter at HA er startet, slik at Companion-handlingene rekker å bli klare. Du kan endre dette til 0–300 sekunder. Installasjon eller vanlig reload av integrasjonen mens HA allerede kjører sender ikke oppstartsvarsel. Testknappen sender en melding merket TEST uten å restarte noe. Deaktivering blokkerer sending; avlasting før ventetiden er utløpt avbryter den planlagte sendingen.

## Dørlås fastkjørt

Legg til **Dørlås fastkjørt**, velg `lock.dorlas_blatann` og behold standard **60 sekunder**. Meldingen blir «Inngangsdørlåsen er fastkjørt og får ikke låst seg.», med `mdi:lock-alert`.

Låsen må være sammenhengende i `jammed` i den valgte tiden. `locked`, `unlocked`, `unknown`, `unavailable` eller en fjernet entitet avbryter nedtellingen. Attributtendringer som batterinivå starter ikke tiden på nytt. Etter ett varsel sendes ingen påminnelser før en ny fastkjøring. Er låsen allerede fastkjørt ved oppstart/reload eller når varselbryteren slås på, observeres en ny full periode før varsel. Testknappen venter ikke og betjener aldri låsen.

Alle tre nye oppsett foreslår iPhone, Pixel og OnePlus hvis de respektive `mobile_app`-handlingene finnes. Mottakere og lyd velges separat per oppsett. Låsvarslet bruker disse eksplisitte mottakerne fremfor den generelle `notify.notify`-handlingen.

Deaktiver de tre gamle automasjonene når de nye oppsettene er testet, ellers kan både gammel og ny løsning sende varsler.

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

Åpne **Varslingsstatus** på integrasjonens enhet. Attributtene viser siste melding, tidspunktet da minst én notify-handling lyktes, og siste sendefeil. «Sendt» betyr at Home Assistant-handlingen lyktes, ikke at telefonen bekreftet levering. Feil på én mottaker stopper ikke forsøket til den andre. Feilen logges også under KI Varslinger og sikkerhet i HA-loggen.

Hvis test virker, men ordinære varsler mangler: kontroller den nye varselbryteren, faktisk tilstandsendring på kilden og eventuelt sonefilter. Har en entitet fått nytt ID, velg den på nytt i Alternativer. Endringer lastes inn uten full omstart.

Ved avinstallering: fjern integrasjonsoppføringene, fjern mappen `custom_components/ki_notifications`, og start HA på nytt. Egne lagrede brytervalg slettes når oppføringen fjernes. De gamle automasjonene kan aktiveres igjen om ønskelig.

## Testgrunnlag og omfang

Kildekode, UI-skjemaer og hendelseshåndtering er testet lokalt med Home Assistant 2025.12.5. Testene bruker HAs ekte tilstandsmaskin og tjenesteregister med simulerte notify-/vacuum-handlinger. De sender ikke til telefoner og kjører ikke en fysisk alarm. Se `TESTING.md` for resultat og kjørekommando.

Installasjon i din HA-instans, nettleservisning, fysisk Roborock og iPhone/Pixel-lyd er ikke testet her. Dette er første versjon. Lysstyringen på soverommet, klimastyringen og nattmodus-kortet er separate funksjoner. Denne integrasjonen samler varsling og de beskrevne sikkerhetsfunksjonene.

## Dørlys – blink ved åpning (2.2.0)

Legg til et nytt oppsett i **KI Varslinger og sikkerhet**, og velg **Dørlys – blink ved åpning**.

| Innstilling | Forslag |
| --- | --- |
| Entitet som skal overvåkes | `lock.dorlas_blatann` – velg låsen som faktisk rapporterer opplåsing |
| Dørsensor | `sensor.inngangsdor` |
| Åpen/lukket sensorverdi | Nøyaktige råverdier fra Utviklerverktøy → Tilstander |
| Lys som skal blinke | `light.pultskjermer` |
| Antall blink | 3 |
| Varighet per av/på-trinn | 0,5 sekunder |
| Maks tid fra opplåsing til åpning | 60 sekunder |

Slå på den nye funksjonsbryteren. Lås opp mens døren er lukket, og åpne den innen tidsgrensen. Integrasjonen må ha observert en reell opplåsing fra låst til ulåst (også via `unlocking`). En dør som allerede står ulåst gir ingen blinking ved åpning. Funksjonen skiller ikke mellom hvem som åpner eller hvilken side de står på.

Lyset blinker tre ganger og går tilbake til rapportert tidligere av/på, lysstyrke og farge. Hvis lyset er en HA-gruppe med medlemsliste, gjenopprettes medlemmenes individuelle tilstander. Ingen blink køes mens en sekvens kjører. Avslått bryter stopper sekvensen og forsøker å gjenopprette lyset.

Status viser **Av**, **Klar**, **Blinker** eller **Sikkerhetsfeil**. Attributtet `siste_blink` viser siste fullførte sekvens i denne kjøretiden. Gjenoppretting krever at lyset fortsatt er tilgjengelig og HA kjører; strømbrudd kan avbryte prosessen. Andre automasjoner eller manuelle lysendringer under blinkingen kan bli overskrevet når den lagrede tilstanden gjenopprettes.

## Testknapper og døravlesning (2.2.0)

Etter oppdatering og omstart kommer knappene og sensorene automatisk på eksisterende Autolås- og Dørlys-enheter. Oppsettet trenger ikke opprettes på nytt.

| Knapp | Virkning |
| --- | --- |
| Test blinking | Blinker nå og gjenoppretter lyset. Fungerer også med automatisk blinking avslått. |
| Kontroller autolås | Kontrollerer rå dørverdi, låstilstand, ventetid og tilgjengelig låsehandling. Låser ikke. |
| Test autolås – lås etter ventetid | Starter vanlig nedtelling. Låser faktisk etter ventetiden hvis døren fortsatt er lukket og låsen er ulåst. Autolås-bryteren må være på. |

En nedtelling som allerede kjører, beholdes. Åpning, ukjent dørverdi eller avslått Autolås avbryter også testnedtellingen. Testresultat-sensoren viser kontrollresultat eller at nedtellingen startet. Se Sikkerhetsstatus og Låsen er låst for endelig resultat; en sendt kommando bekrefter ikke fysisk låsing.

| Sensor | På / true | Av / false | Ukjent |
| --- | --- | --- | --- |
| Dørverdi gjenkjent | Råverdien matcher konfigurert åpen eller lukket | Manglende/ukjent eller annen råverdi | — |
| Døren er lukket | Matcher lukket-verdi | Matcher åpen-verdi | Ingen gjenkjent dørverdi |
| Låsen er låst | Låsen rapporterer locked | Låsen rapporterer unlocked | Låsen mangler, er utilgjengelig eller har en mellom-/feiltilstand |

Home Assistant viser disse som På/Av (råtilstand on/off); attributtet `tolket_verdi` er true/false eller null. `kilde` og `raverdi` viser hva integrasjonen leser. Verdiene oppdateres også når automatikkbryteren er av. Åpne og lukk døren fysisk for å kontrollere at visningen følger riktig vei. Gjenkjent verdi bekrefter samsvar med oppsettet, ikke at sensoren er fysisk korrekt eller koblet til riktig dør.
