# KI Varslinger og sikkerhet 2.4.0

- **Stedsnavn som tittel i familievarslene:** kjører du Home Assistant på flere steder, kan tittelen si hvilket hus varselet kom fra. «Toten» på første linje, «Cybele forlot huset.» på linjen under.
- To nye innstillinger på familieoppsettet: **Vis stedsnavn som tittel** (av som standard) og **Stedsnavn**. Tomt navnefelt bruker navnet på Home Assistant-serveren, satt under Innstillinger → System → Generelt.
- Er både overstyringen og servernavnet tomt, brukes den vanlige tittelen «🚶 Forlot huset» / «🏠 Kom hjem». Avslått bryter gir uendret oppførsel, så eksisterende oppsett ser likt ut etter oppdatering.
- Valget gjelder per familieoppsett og brukes også av testknappene. Andre varseltyper har uendret tittel.

80 tester bestått i et isolert HA-miljø med simulerte tjenester, inkludert publiseringstesten. Telefonvisning er ikke testet her; kontroller hvordan tittelen ser ut på iPhone og Android etter oppdatering.
