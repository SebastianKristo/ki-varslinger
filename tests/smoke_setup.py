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
  h.config.components.add('webhook')
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
  for kind, settings, expected_count in [
   ('autolock',{'entity':'lock.front','door_entity':'sensor.door','door_open':'open','door_closed':'closed','autolock_delay':30},3),
   ('face_unlock',{'entity':'lock.front',**{'webhook_'+p:'smoke_only_'+p+'_xxxxxxxxxxxxxxxxxxxx' for p in ['rune','cybele','sebastian']}},3),
  ]:
   extra=config_entries.ConfigEntry(version=1,minor_version=1,domain='ki_notifications',title=kind,data={'kind':kind,'name':kind,**settings},options={},source='user',unique_id=None,discovery_keys={},subentries_data=[])
   await h.config_entries.async_add(extra)
   await h.async_block_till_done()
   own_extra=entity_registry.async_entries_for_config_entry(entity_registry.async_get(h),extra.entry_id)
   assert len(own_extra)==expected_count, (kind,extra.state,len(own_extra))
   assert not h.data['ki_notifications'][extra.entry_id].enabled['enabled']
   assert await h.config_entries.async_unload(extra.entry_id)
   print(kind, 'SETUP AND UNLOAD OK')
  assert not h.data.get('webhook',{})
  assert await h.config_entries.async_unload(entry.entry_id)
  print('UNLOAD OK')
  await h.async_stop()
if __name__ == '__main__':
 asyncio.run(main())
