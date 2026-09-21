"""Tester for den redigerbare værmeldingen.

Logikken er liten, men konsekvensen av en feil er stor: bommer vi på plassholderen,
sender vi en prompt uten værdata — og da finner modellen på været i stedet for å si
at data mangler.

Skrevet med unittest, ikke pytest: CI kjører `python -m unittest discover`, og der er
pytest ikke installert. Med `import pytest` øverst kunne ikke modulen engang lastes, og
hele testjobben ble rød fra 2.5.0 – uten at én eneste test faktisk feilet.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT))

# Standardtekstene hentes fra selve integrasjonen, så testen ikke tester en kopi som
# kan gli fra originalen. const.py trekker ikke inn Home Assistant.
from custom_components.ki_notifications.const import (  # noqa: E402
    WEATHER_ICON,
    WEATHER_PROMPT,
    WEATHER_TITLE,
)


# Samme tre linjer som i extra_notifications.weather_notice.
def bygg_instruks(cfg, facts):
    mal = (cfg.get("prompt") or WEATHER_PROMPT).strip() or WEATHER_PROMPT
    fakta = json.dumps(facts, ensure_ascii=False)
    return mal.replace("{data}", fakta) if "{data}" in mal else mal + "\n" + fakta


def tittel(cfg):
    return (cfg.get("title") or WEATHER_TITLE).strip() or WEATHER_TITLE


def ikon(cfg):
    return (cfg.get("icon") or WEATHER_ICON).strip() or WEATHER_ICON


FAKTA = {"temperatur": 13.4, "temperaturenhet": "°C", "nedbør": 0.2}


class Vaerprompt(unittest.TestCase):
    def test_standarden_er_uendret(self):
        """Et oppsett uten de nye feltene skal se nøyaktig ut som før."""
        i = bygg_instruks({}, FAKTA)
        self.assertTrue(i.startswith("Lag en hyggelig og informativ værmelding"))
        self.assertIn("13.4", i)
        self.assertEqual(tittel({}), "God morgen ☀️")
        self.assertEqual(ikon({}), "mdi:weather-partly-cloudy")

    def test_egen_prompt_brukes(self):
        i = bygg_instruks({"prompt": "Skriv ett kort vers om været. {data}"}, FAKTA)
        self.assertTrue(i.startswith("Skriv ett kort vers"))
        self.assertIn("13.4", i)

    def test_data_legges_til_uten_plassholder(self):
        """Glemmer man {data}, skal dataene likevel med – ellers finner modellen på været."""
        i = bygg_instruks({"prompt": "Skriv noe hyggelig om været."}, FAKTA)
        self.assertTrue(i.startswith("Skriv noe hyggelig"))
        self.assertIn("13.4", i)
        self.assertGreaterEqual(i.count("temperatur"), 1)

    def test_plassholder_flere_steder(self):
        i = bygg_instruks({"prompt": "Før {data} etter {data}"}, {"a": 1})
        self.assertEqual(i.count('"a": 1'), 2)

    def test_tomme_felt_faller_tilbake(self):
        """Tømmer man feltet i brukerflaten, skal standarden gjelde — ikke ingenting."""
        for tom in ("", "   ", None):
            with self.subTest(tom=tom):
                self.assertTrue(bygg_instruks({"prompt": tom}, FAKTA).startswith("Lag en hyggelig"))
                self.assertEqual(tittel({"title": tom}), "God morgen ☀️")
                self.assertEqual(ikon({"icon": tom}), "mdi:weather-partly-cloudy")

    def test_egen_tittel_og_ikon(self):
        self.assertEqual(tittel({"title": "Været i dag"}), "Været i dag")
        self.assertEqual(ikon({"icon": "mdi:weather-sunny"}), "mdi:weather-sunny")

    def test_norske_tegn_overlever(self):
        """æøå og ° skal ikke bli til \\u-koder i prompten."""
        i = bygg_instruks({}, {"tilstand": "delvis skyet", "temperatur": "13°C"})
        self.assertIn("delvis skyet", i)
        self.assertIn("13°C", i)
        self.assertNotIn("\\u", i)

    def test_dataene_er_gyldig_json(self):
        """Modellen skal kunne lese dem. En streng med anførselstegn ville brutt det."""
        i = bygg_instruks({"prompt": "{data}"}, {"tekst": 'han sa "hei"', "n": None})
        json.loads(i)

    def test_logikken_i_integrasjonen_er_den_samme(self):
        """Testen over bruker en kopi av tre linjer fra weather_notice. Står de ikke
        lenger i integrasjonen, tester kopien noe som ikke finnes – da skal dette feile."""
        kilde = (ROT / "custom_components/ki_notifications/extra_notifications.py").read_text(encoding="utf-8")
        for linje in ("(c.get('prompt') or WEATHER_PROMPT).strip() or WEATHER_PROMPT",
                      "mal.replace('{data}', fakta) if '{data}' in mal",
                      "(c.get('title') or WEATHER_TITLE).strip() or WEATHER_TITLE",
                      "(c.get('icon') or WEATHER_ICON).strip() or WEATHER_ICON"):
            self.assertIn(linje, kilde)


if __name__ == "__main__":
    unittest.main()
