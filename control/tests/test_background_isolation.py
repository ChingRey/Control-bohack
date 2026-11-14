import copy
import threading
import time
import unittest
from unittest.mock import patch
import backend as b
import test_checkpoints as fixture
from agents import workflow_records as wr, teaching_evolution as e
from test_teaching_evolution import task as episode_task, result as episode_result


class BackgroundIsolationTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
  t=b.load(self.h.task['id']);t['workflow']['auto_organize']=False;b.save(t)

 def wait_run(self,key):
  for _ in range(300):
   t=b.load(self.h.task['id']);run=e.state(t)['run'] if key=='experience' else t.get(key,{})
   if run.get('status') not in ('running','queued'):return t
   time.sleep(.01)
  self.fail('background did not finish')

 def test_organizer_merges_proposals_without_replacing_new_material_or_chat(self):
  entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
  def organize(work):
   entered.set();release.wait(3)
   wr.candidates(work,{'items':[{'kind':'requirements','content':'old-snapshot suggestion','evidence_ids':[0],
    'quotes':[{'message_id':0,'quote':work['messages'][0]['content']}]}]},[0])
  with patch.object(wr,'organize',side_effect=organize):
   t=b.load(self.h.task['id']);b.start_organizer(t);self.assertTrue(entered.wait(1))
   with b.task_lock(t['id']):
    fresh=b.load(t['id']);fresh['messages'].append({'role':'user','channel':'teaching','content':'new statement'})
    fresh['workflow']['materials']['requirements'].append({'revision':20,'content':'newly confirmed'})
    fresh['workflow']['revision']+=1;b.save(fresh)
   release.set();fresh=self.wait_run('organizer_run')
  self.assertEqual(fresh['organizer_run']['status'],'completed')
  self.assertEqual(fresh['workflow']['materials']['requirements'][-1]['content'],'newly confirmed')
  self.assertEqual(fresh['messages'][-1]['content'],'new statement')
  self.assertEqual(fresh['workflow']['proposals'][-1]['content'],'old-snapshot suggestion')
  self.assertTrue(fresh['workflow']['proposals'][-1]['background_snapshot'])

 def test_active_organizer_does_not_block_coding_or_normal_actions(self):
  entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
  def organize(work):entered.set();release.wait(3)
  with patch.object(wr,'organize',side_effect=organize),patch.object(b.opencode_executor,'execute',side_effect=self.h.execute):
   t=b.load(self.h.task['id']);t['checkpoint_delivery']='manual';b.save(t);b.start_organizer(t)
   self.assertTrue(entered.wait(1));self.assertFalse(b.task_busy(b.load(t['id'])))
   self.assertEqual(self.h.call(self.h.path+'/workflow/options',{'mode':'free','auto_organize':False})[0],200)
   self.assertEqual(self.h.call(self.h.path+'/chat/send',{'channel':'coding','message':'修改商品列表','request_id':'independent-chat'})[0],202)
   fresh=self.h.wait();self.assertEqual(fresh['coding_run']['status'],'completed')
   self.assertEqual(fresh['organizer_run']['status'],'running')
   release.set();self.wait_run('organizer_run')

 def test_proposal_append_does_not_stale_foreground_but_confirmed_change_does(self):
  t=b.load(self.h.task['id']);baseline=b.task_signature(t)
  t['workflow'].setdefault('proposals',[]).append({'id':'new-background-proposal','content':'pending'})
  self.assertEqual(b.task_signature(t),baseline)
  t['workflow']['revision']+=1;self.assertNotEqual(b.task_signature(t),baseline)

 def test_changed_original_evidence_is_rejected(self):
  t=b.load(self.h.task['id']);rows=e.eligible(t);t['messages'][0]['content']='changed'
  self.assertFalse(b.background_sources_match(t,rows))

 def test_reflection_survives_code_edit_and_keeps_new_loads(self):
  entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
  def analyze(*args):entered.set();release.wait(3);return episode_result()
  t=b.load(self.h.task['id']);sample=episode_task();t['messages']=sample['messages'];t['teaching_evolution']=sample['teaching_evolution'];t['teaching_evolution']['auto']=False;b.save(t)
  with patch.object(b.teaching.TeachingAgent,'mode',new_callable=lambda:property(lambda self:'model')),patch.object(e,'analyze',side_effect=analyze):
   b.start_experience_review(t);self.assertTrue(entered.wait(1))
   with b.task_lock(t['id']):
    fresh=b.load(t['id']);fresh['messages'].append({'role':'user','channel':'coding','content':'new change'})
    e.state(fresh)['loads'].append({'reply_message_id':999,'entries':[]});b.save(fresh)
    b.write_project_file(b.project(t['id'])/'new.js','// next version')
   release.set();fresh=self.wait_run('experience')
  self.assertEqual(e.state(fresh)['run']['status'],'completed')
  self.assertEqual(e.state(fresh)['loads'][-1]['reply_message_id'],999)
  self.assertEqual(fresh['messages'][-1]['content'],'new change')
  self.assertEqual(e.state(fresh)['cursor'],2)
  self.assertEqual(b.read_project_files(t['id'])['new.js'],'// next version')

 def test_timeout_is_not_masked_by_new_chat_and_partial_evaluation_survives(self):
  entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
  t=b.load(self.h.task['id']);sample=episode_task();t['messages']=sample['messages'];t['teaching_evolution']=sample['teaching_evolution'];t['teaching_evolution']['auto']=False;b.save(t)
  def analyze(work,review):
   work['_experience_progress']('evaluation_ready',{'evaluation':episode_result()['evaluation'],'scores':[],'detail':'评价已完成'})
   entered.set();release.wait(3);raise TimeoutError('sensitive underlying data')
  with patch.object(b.teaching.TeachingAgent,'mode',new_callable=lambda:property(lambda self:'model')),patch.object(e,'analyze',side_effect=analyze):
   b.start_experience_review(t);self.assertTrue(entered.wait(1))
   with b.task_lock(t['id']):
    fresh=b.load(t['id']);fresh['messages'].append({'role':'user','channel':'teaching','content':'continued learning'});b.save(fresh)
   release.set();fresh=self.wait_run('experience')
  run=e.state(fresh)['run'];self.assertEqual(run['status'],'failed');self.assertEqual(run['error_code'],'provider_timeout')
  self.assertIn('evaluation',run);self.assertEqual(e.state(fresh)['cursor'],-1)
  self.assertEqual(fresh['background_run_history'][-1]['error_code'],'provider_timeout')
  self.assertNotIn('sensitive underlying data',str(fresh))

 def test_experience_revision_conflict_archives_result_instead_of_dropping_it(self):
  entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
  t=b.load(self.h.task['id']);sample=episode_task();t['messages']=sample['messages'];t['teaching_evolution']=sample['teaching_evolution'];t['teaching_evolution']['auto']=False;b.save(t)
  def analyze(work,review):entered.set();release.wait(3);return episode_result()
  with patch.object(b.teaching.TeachingAgent,'mode',new_callable=lambda:property(lambda self:'model')),patch.object(e,'analyze',side_effect=analyze):
   b.start_experience_review(t);self.assertTrue(entered.wait(1))
   with b.task_lock(t['id']):
    fresh=b.load(t['id']);e.manage(fresh,{'action':'options','mode':'observe','auto':False,'expected_revision':0});b.save(fresh)
   release.set();fresh=self.wait_run('experience')
  run=e.state(fresh)['run'];self.assertEqual(run['status'],'conflict');self.assertEqual(run['error_code'],'playbook_changed')
  self.assertIn('unapplied_result',run);self.assertEqual(e.state(fresh)['mode'],'observe');self.assertEqual(len(e.state(fresh)['reviews']),0)
