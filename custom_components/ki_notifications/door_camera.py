"""Dørvarsel med kamerabilde: låst, låst opp, åpnet og lukket.

Varselet får et bilde fra kameraet ved døra, tatt litt etter at hendelsen skjedde –
så den som kom inn faktisk er i bildet, ikke bare en tom gang.

To måter å levere bildet på:

* **Direkte (proxy)** – standard. Varselet peker på /api/camera_proxy/<kamera>, og
  appen henter bildet selv, med innloggingen sin. Ingenting lagres på disk, og
  ingenting blir liggende åpent på nettet. Bildet er det kameraet ser idet telefonen
  henter det, som i praksis er et sekund eller to etter hendelsen.
* **Lagret bilde (snapshot)** – et stillbilde tas med camera.snapshot i det øyeblikket
  og legges i www/ki_varslinger/ med et tilfeldig navn. Da er bildet nøyaktig fra
  hendelsen, men /local/ er åpent for alle som kjenner adressen, og Home Assistant må
  ha www-mappa i allowlist_external_dirs. Feiler lagringen, faller varselet tilbake
  på proxy i stedet for å komme uten bilde.

Flere hendelser tett etter hverandre (låst opp, så åpnet) samles i ett varsel som
oppdateres, i stedet for tre varsler med tre bilder på et halvt minutt.
"""

import asyncio
import os
import secrets
import time

from homeassistant.util import dt as dt_util

from .const import INVALID

# Hendelse → (tittel, kort tekst i sammendraget, ikon)
DOOR_EVENTS = {
    'locked': ('🔒 Døra ble låst', 'låst', 'mdi:lock'),
    'unlocked': ('🔓 Døra ble låst opp', 'låst opp', 'mdi:lock-open-variant'),
    'opened': ('🚪 Døra ble åpnet', 'åpnet', 'mdi:door-open'),
    'closed': ('🚪 Døra ble lukket', 'lukket', 'mdi:door-closed'),
}

# Låsens tilstander. Mellomtilstandene (locking/unlocking/opening) gir ikke varsel –
# vi venter på at låsen har landet.
LOCKED = {'locked'}
UNLOCKED = {'unlocked', 'open'}

SNAPSHOT_KEEP = 20
SNAPSHOT_DIR = 'ki_varslinger'


class DoorCamera:
    def door_camera_init(self):
        self.door_log = []          # [(monotonisk tid, hendelse, klokkeslett)]
        self.door_tag = None
        self.door_tag_until = 0.0
        self.door_tasks = set()

    def door_camera_close(self):
        for task in list(self.door_tasks):
            task.cancel()
        self.door_tasks.clear()

    # ---- hendelser ------------------------------------------------------

    async def door_camera_changed(self, old, new, entity_id):
        """Kalles under self.lock. Finner hendelsen og sender varselet utenfor låsen."""
        if old is None or new is None or old.state in INVALID or new.state in INVALID:
            return
        if old.state == new.state:
            return
        c = self.cfg
        event = None
        if entity_id == c.get('entity'):
            if new.state in LOCKED and old.state not in LOCKED:
                event = 'locked'
            elif new.state in UNLOCKED and old.state not in UNLOCKED:
                event = 'unlocked'
        elif entity_id == c.get('door_entity'):
            if new.state == c.get('door_open', 'open'):
                event = 'opened'
            elif new.state == c.get('door_closed', 'closed'):
                event = 'closed'
        if event is None or not self.enabled.get(event, False):
            return
        who = None
        if event in {'locked', 'unlocked'}:
            who = new.attributes.get('changed_by') or None
        self.door_schedule(event, who)

    def door_schedule(self, event, who=None, test=False):
        """Bildet tas litt etter hendelsen, så den som kom står i bildet. Sendingen går
        som egen oppgave: ellers ville låsen blitt holdt i ventetiden, og en «åpnet»
        rett etter «låst opp» måtte stått i kø."""
        now = time.monotonic()
        window = float(self.cfg.get('group_seconds', 60) or 0)
        if not test and (self.door_tag is None or now > self.door_tag_until or window <= 0):
            self.door_log = []
            self.door_tag = f'ki_door_{self.entry.entry_id}_{secrets.token_hex(4)}'
        if not test:
            self.door_tag_until = now + window
            stamp = dt_util.now().strftime('%H:%M')
            self.door_log.append((now, event, stamp, who))
        delay = max(0.0, float(self.cfg.get('image_delay', 1) or 0))

        async def later():
            try:
                if delay:
                    await asyncio.sleep(delay)
                await self.door_notice(event, who=who, test=test)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 – vises i statusentiteten
                self.last_error = f'dørvarsel: {err}'
                self.update()

        task = self.hass.async_create_task(later())
        self.door_tasks.add(task)
        task.add_done_callback(self.door_tasks.discard)
        return task

    # ---- bildet ---------------------------------------------------------

    def door_proxy_url(self):
        camera = self.cfg.get('camera')
        if not camera:
            return None
        # Tidsstempelet hindrer at appen viser et bilde den har mellomlagret fra forrige
        # varsel med samme adresse.
        return f'/api/camera_proxy/{camera}?ki={int(time.time())}'

    async def door_snapshot_url(self):
        """Tar et stillbilde og returnerer /local-adressen, eller None om det feilet."""
        camera = self.cfg.get('camera')
        folder = self.hass.config.path('www', SNAPSHOT_DIR)
        name = f'{secrets.token_urlsafe(16)}.jpg'
        path = os.path.join(folder, name)
        await self.hass.async_add_executor_job(lambda: os.makedirs(folder, exist_ok=True))
        await asyncio.wait_for(self.hass.services.async_call(
            'camera', 'snapshot', {'entity_id': camera, 'filename': path}, blocking=True), timeout=15)
        await self.hass.async_add_executor_job(self._door_cleanup, folder)
        return f'/local/{SNAPSHOT_DIR}/{name}'

    @staticmethod
    def _door_cleanup(folder):
        """Beholder de nyeste bildene; resten slettes, så mappa ikke vokser for alltid."""
        try:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.jpg')]
        except FileNotFoundError:
            return
        files.sort(key=os.path.getmtime, reverse=True)
        for old in files[SNAPSHOT_KEEP:]:
            try:
                os.remove(old)
            except OSError:
                pass

    async def door_image(self):
        """Adressen varselet skal peke på, etter valgt modus – med proxy som reserve."""
        if not self.cfg.get('camera'):
            return None
        if self.cfg.get('image_mode', 'proxy') == 'snapshot':
            try:
                return await self.door_snapshot_url()
            except Exception as err:  # noqa: BLE001
                self.last_source_error = (
                    f'camera.snapshot: {err} – sendte direktebilde i stedet. '
                    'Lagret bilde krever at www-mappa står i allowlist_external_dirs.')
        return self.door_proxy_url()

    # ---- varselet -------------------------------------------------------

    def door_message(self, event, who=None, test=False):
        title, _short, icon = DOOR_EVENTS[event]
        if test:
            return title, f"TEST: {title[2:].strip()}.", icon
        # Ett varsel for det som skjedde i samme vindu: «Låst opp 14:32 · åpnet 14:32».
        parts = []
        for _t, ev, stamp, by in self.door_log:
            text = DOOR_EVENTS[ev][1]
            if by and ev in {'locked', 'unlocked'}:
                text += f' av {by}'
            parts.append(f'{text} {stamp}')
        message = ' · '.join(parts) if parts else DOOR_EVENTS[event][1]
        message = message[0].upper() + message[1:] + '.'
        return title, message, icon

    async def door_notice(self, event, who=None, test=False):
        title, message, icon = self.door_message(event, who, test)
        image = await self.door_image()
        extra = {}
        if image:
            extra['image'] = image
        ios_extra = {}
        if self.cfg.get('camera') and self.cfg.get('live_ios', True):
            # Holder du inne varselet på iPhone, vises kameraet direkte.
            ios_extra['entity_id'] = self.cfg['camera']
        await self.send(title, message, icon, tag=None if test else self.door_tag,
                        test=test, extra=extra, ios_extra=ios_extra)
