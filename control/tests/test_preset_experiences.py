import copy,json,sqlite3,unittest
from pathlib import Path
from agents import experience_library as lib,teaching_evolution as e

class PresetExperienceTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.addCleanup(self.c.close);self.c.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,body TEXT)')
 def test_catalog_has_complete_fields_and_real_sources(self):
  import hashlib
  from agents.experience_evidence import ITEMS
  catalog=e.asset('presets-from-code-v1.json');self.assertEqual(len(catalog['entries']),15)
  for entry in catalog['entries']:
   for key in ('title','when','action','verify','limits','tags','source','source_refs','rationale','example','evidence_plan'):self.assertTrue(entry[key])
   for source in entry['source_refs']:
    path=Path(source['path']);self.assertTrue(path.is_file());self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),source['sha256'])
   for observation in entry['evidence_plan']:
    self.assertIn(observation['item_id'],[x[0] for x in ITEMS[observation['dimension']]])
 def test_existing_seed_preserved_and_migration_is_once(self):
  state=e.state({});state.update(scope='shared-demo',batches=[]);seed=state['entries'][0];seed.update(status='inactive',action='已人工修改的动作')
  self.c.execute('CREATE TABLE experience_library(id INTEGER PRIMARY KEY,body TEXT)');self.c.execute('INSERT INTO experience_library VALUES(1,?)',(lib.encode(state),))
  book=lib.read(self.c);self.assertEqual(len(book['entries']),15);self.assertEqual(book['revision'],1)
  self.assertEqual(book['entries'][0]['action'],'已人工修改的动作');self.assertEqual(book['entries'][0]['status'],'inactive')
  self.assertTrue(book['entries'][0]['source_refs']);self.assertEqual(lib.read(self.c),book)
  self.assertEqual(sum(x['status']=='trial' for x in book['entries']),10)
  self.assertTrue(all(x['verified'] is False for x in book['entries']))
 def test_import_is_reversible_and_undo_never_reimports(self):
  book=lib.read(self.c);batch=book['batches'][-1]
  restored=lib.manage(self.c,{'expected_revision':book['revision'],'action':'undo','batch_id':batch['id']})
  self.assertTrue(all(x['status']=='inactive' for x in restored['entries'] if x.get('origin')=='preset'))
  self.assertEqual(lib.read(self.c),restored)
  again=lib.manage(self.c,{'expected_revision':restored['revision'],'action':'restore','target_revision':0})
  self.assertEqual(len(again['entries']),5);self.assertEqual(lib.read(self.c),again)
 def test_selected_preset_has_observation_focus_and_can_be_stopped(self):
  book=lib.read(self.c);t={'id':'new','plan':[],'step':0,'messages':[{'channel':'teaching','role':'user','content':'我想做一个小游戏，第一版范围如何确定'}]};lib.attach(self.c,t)
  packet=e.packet(t);self.assertIsNotNone(packet['validation_focus']);focus=packet['validation_focus'];self.assertTrue(focus['example']);self.assertTrue(focus['evidence_plan'])
  lib.manage(self.c,{'expected_revision':book['revision'],'action':'status','entry_id':focus['entry_id'],'status':'inactive'});lib.attach(self.c,t)
  self.assertNotIn(focus['entry_id'],[x['id'] for x in e.packet(t)['entries']])
 def test_reflection_candidate_priority_does_not_force_unrelated_presets(self):
  t={'id':'new','plan':[],'step':0,'messages':[{'channel':'teaching','role':'user','content':'一种完全不匹配的内容XYZ'}]};lib.attach(self.c,t)
  self.assertIsNone(e.packet(t)['validation_focus'])
