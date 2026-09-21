# KI Varslinger og sikkerhet 2.6.0

## Ny regel: dør låst/åpnet med kamerabilde

Varsel når inngangsdøra låses, låses opp, åpnes eller lukkes — med bilde fra kameraet ved døra.

Legg til et nytt oppsett og velg **Dør – låst/åpnet med kamerabilde**. Låsen og dørsensoren fylles ut
av seg selv, og kameraet gjettes ut fra navnet.

- **Fire brytere**, én per hendelse, pluss **Alle varsler**. «Døra lukket» er av fra start.
- **Bildet tas litt etter hendelsen** (standard 1 s), så den som kom står i bildet — ikke bare en
  tom gang. Sendingen går som egen oppgave, så ventetiden holder ikke igjen neste hendelse.
- **Direkte kamera på iPhone:** holder du inne varselet, vises kameraet live.
- **Ett varsel, ikke tre:** låst opp og åpnet innen 60 s blir ett varsel som oppdateres —
  «Låst opp 14:32 · åpnet 14:32». 0 gir ett varsel per hendelse.
- **Hvem:** oppgir låsen `changed_by`, står det i teksten — «Låst av Sebastian».
- Låsens mellomtilstander (`locking`, `unlocking`) og overgangen fra `unavailable` etter omstart gir
  ikke varsel.

### To måter å levere bildet på

| | Direkte fra kameraet (standard) | Lagret stillbilde |
| --- | --- | --- |
| Hvordan | Varselet peker på `/api/camera_proxy/<kamera>`; appen henter med innloggingen sin | `camera.snapshot` til `www/ki_varslinger/`, tilfeldig filnavn |
| Tidspunkt | Når telefonen henter bildet, et sekund eller to etter | Nøyaktig øyeblikket |
| Lagring | Ingenting | De 20 nyeste beholdes, resten slettes |
| Krav | Ingen | Mappa i `allowlist_external_dirs`; `/local/` er åpent for den som kjenner adressen |

Feiler lagringen, sendes varselet med direktebilde i stedet for uten bilde, og årsaken står i
statusentiteten.

### Samtidig rettet

`tests/test_publish_script.py` hadde `2.2.0` hardkodet igjen. Publiseringsskriptet nekter å pakke ut en
zip der manifestet har en annen versjon, så testen feilet ved hver versjonsbump — men bare på
maskiner med `rsync`; ellers ble den hoppet over og så grønn ut. Rettingen fra 2.3.1 hadde falt ut
underveis. Versjonen leses nå fra `manifest.json` igjen.

`entity.py` sto fortsatt på `sw_version='2.2.0'`; den følger manifestet igjen (2.6.0).

### Kontrollert

90 tester, alle bestått og **ingen hoppet over** — publiseringstesten kjøres nå med `rsync`. 16 nye i
`tests/test_door_camera.py`: brytere og standardverdier, skjema og feilmeldinger, bilde til begge
plattformer og live-kamera bare til iPhone, `changed_by`, mellomtilstander og `unavailable`,
dørsensor åpnet/lukket, enkeltbrytere og hovedbryter, samlet varsel og vindu 0, lagret bilde,
reserve til direktebilde når lagringen feiler, opprydding til 20 filer og testknappen.
`test_master_only_for_multiple_toggles` er utvidet med den nye regelen, som har fire brytere og
dermed hovedbryter.

Innlastingstesten (`tests/smoke_setup.py`) er ikke kjørt: den krever Home Assistant 2025.12, og
miljøet her har 2025.1. Notify og kamera er simulert — ikke testet mot en ekte telefon eller et
ekte kamera.
