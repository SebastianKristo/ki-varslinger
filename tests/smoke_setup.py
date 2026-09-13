"""Core load/unload smoke test. Companion transport is simulated; pip installs disabled in this test only."""
import asyncio,tempfile,shutil
from pathlib import Path
from homeassistant.core import HomeAssistant
from homeassistant import loader, config_entries
from homeassistant.setup import async_setup_component
from homeassistant.helpers import entity_registry, device_registry, area_registry, floor_registry, label_registry

async def main():
 with tempfile.TemporaryDirectory() as root:
  shutil.copytree(Path(__file__).resolve().parents[1]/'custom_components',Path(root)/'custom_components',ignore=shutil.ignore_patterns('__pycache__'))
  h=HomeAssistant(root); h.config.skip_pip=True; loader.async_setup(h)
  h.config_entries=config_entries.ConfigEntries(h,{})
  await h.config_entries.async_initialize()
  for reg in [entity_registry,device_registry,area_registry,floor_registry,label_registry]: await reg.async_load(h)
  h.config.components.add('mobile_app')
  sent=[]
  async def notify(call):sent.append(dict(call.data))
  h.services.async_register('notify','mobile_app_test',notify)
  for p in ['rune','cybele','sebastian']:h.states.async_set('switch.'+p,'off')
  entry=config_entries.ConfigEntry(version=1,minor_version=1,domain='ki_notifications',title='Familie',data={'kind':'family','name':'Familie','ios_targets':['mobile_app_test'],'android_targets':[],**{p:'switch.'+p for p in ['rune','cybele','sebastian']}},options={},source='user',unique_id=None,discovery_keys={},subentries_data=[])
  await asyncio.wait_for(h.config_entries.async_add(entry),30)
  await h.async_block_till_done()
  print('ENTRY STATE',entry.state)
  own=entity_registry.async_entries_for_config_entry(entity_registry.async_get(h),entry.entry_id)
  print('ENTITIES',len(own))
  assert len(own)==10
  h.states.async_set('switch.rune','on');await h.async_block_till_done()
  assert sent[-1]['message']=='Rune kom hjem.'
  print('EVENT NOTIFICATION OK')
  flow=await h.config_entries.options.async_init(entry.entry_id)
  assert flow['type']=='form'
  print('OPTIONS FORM OK')
  assert await h.config_entries.async_unload(entry.entry_id)
  print('UNLOAD OK')
  await h.async_stop()
if __name__ == '__main__':
 asyncio.run(main())
