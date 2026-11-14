import copy
import json
import os
import time
import unittest
from unittest.mock import patch
from agents import teaching_library as lib,teaching,workflow_records as wr,memory,opencode_executor
import backend as b
import test_checkpoints as fixture

def task(message='为什么刷新后数据没了？',stage=1,mode='guided'):
 return {'id':'library-test','mode':'opencode','title':'Counter','plan':[],'plan_draft':[],'step':0,'files':{'index.html':'<button>0</button>'},'changes':[],'checks':[],
  'messages':[{'channel':'teaching','role':'user','content':message}],
  'workflow':{'revision':0,'stage':stage,'feature':'','mode':mode,'materials':{n:[] for n in ('requirements','design','experiences','coverage','learner')},'events':[]}}

class TeachingLibraryTests(unittest.TestCase):
 def test_catalog_is_integral_and_lessons_have_curated_sources(self):
  data=lib.catalog();ids={s['id'] for s in data['sources']}
  self.assertEqual(len(data['lessons']),21);self.assertEqual(len(ids),31)
  self.assertFalse(data['effectiveness_validated']);self.assertNotIn('R30',ids);self.assertNotIn('R27',ids)
  self.assertTrue(all(set(c['source_ids'])<=ids for c in data['lessons']))
 def test_specific_question_wins_over_current_stage_and_queued_message(self):
  t=task('请解释localStorage和刷新',stage=0)
  t['messages'].append({'channel':'teaching','role':'user','content':'请讲密钥权限','queue_status':'queued'})
  packet=lib.packet(t)
  self.assertEqual(packet['lessons'][0]['id'],'L09');self.assertNotIn('L18',[c['id'] for c in packet['lessons']])
 def test_defer_free_mode_and_explicit_choice_do_not_force_lessons(self):
  t=task('看看当前项目',stage=1);lib.choose(t,'L03','later')
  self.assertNotIn('L03',[c['id'] for c in lib.packet(t)['lessons']])
  t['workflow']['mode']='free';self.assertEqual(lib.packet(t)['lessons'],[])
  lib.choose(t,'L09','learn');self.assertEqual(lib.packet(t)['lessons'][0]['id'],'L09')
  t['messages'][0]['content']='先不学，我只想开发';self.assertEqual(lib.packet(t)['lessons'],[])
  self.assertFalse(lib.trace(lib.packet(t))['mastery_certified'])
 def test_defer_does_not_reopen_from_old_question_but_allows_new_request(self):
  t=task('为什么刷新后数据没了？');lib.choose(t,'L09','later')
  self.assertNotIn('L09',[c['id'] for c in lib.packet(t)['lessons']])
  t['messages'].append({'channel':'teaching','role':'user','content':'现在请解释localStorage是什么'})
  self.assertIn('L09',[c['id'] for c in lib.packet(t)['lessons']])
 def test_packet_budget_and_selection_do_not_mutate_task(self):
  t=task();before=copy.deepcopy(t)
  self.assertLessEqual(lib.size(lib.packet(t,budget=2200)),2200)
  self.assertEqual(lib.packet(t,budget=1),{})
  self.assertEqual(t,before)
 def test_learning_greeting_does_not_automatically_start_a_quiz(self):
  for text in ('你好','我懂了','继续开发'):
   self.assertEqual(lib.packet(task(text))['lessons'],[])
 def test_real_adapter_request_includes_selected_card_and_readonly_policy(self):
  t=task();before=copy.deepcopy(t['files']);seen=[]
  def request(config,messages,*a,**kw):seen.append((copy.deepcopy(messages),kw));return None
  answer={'choices':[{'message':{'content':'先区分页面内存与localStorage，再核对刷新操作。'}}]}
  with patch.dict(os.environ,{'TEACHING_MODE':'model','TEACHING_API_KEY':'fixture-key','TEACHING_MODEL':'fixture-model'}),patch.object(teaching.memory,'prepare'),patch.object(teaching.providers,'request',side_effect=request),patch.object(teaching,'request_model',return_value=answer):teaching.run(t)
  ctx=json.loads(seen[0][0][1]['content'])
  self.assertEqual(ctx['teaching_library']['lessons'][0]['id'],'L09')
  self.assertIn('按来源',ctx['teaching_library']['lessons'][0]['concept_explanation'])
  self.assertTrue(ctx['teaching_library']['lessons'][0]['suggested_checks'])
  self.assertIn('无限反问',seen[0][0][0]['content'])
  self.assertEqual({r['function']['name'] for r in seen[0][1]['tools']},{'read_project_file','read_message_history'})
  trace=t['teaching']['turns'][-1]['teaching_library'];self.assertTrue(trace['submitted_to_model']);self.assertIn('R21',trace['source_ids'])
  self.assertFalse(trace['application_verified']);self.assertEqual(t['files'],before)
 def test_sample_never_records_real_model_submission(self):
  t=task()
  with patch.dict(os.environ,{'TEACHING_MODE':'sample'}):teaching.run(t)
  self.assertFalse(t['teaching']['turns'][-1]['teaching_library']['submitted_to_model'])
 def test_organizer_does_not_accept_literature_ids_as_student_evidence(self):
  t=task();wr.initialize(t)
  row={'kind':'concept','content':'存储讲解','concept':'存储','level':'explained','evidence_ids':['R21'],'quotes':[{'message_id':'R21','quote':'storage'}]}
  with self.assertRaises(ValueError):wr.candidates(t,{'items':[row]},[0])
  self.assertEqual(t['workflow']['concepts']['存储']['status'],'unknown')
 def test_permissions_and_timeout_unchanged(self):
  self.assertEqual(opencode_executor.permissions()['write'],'allow');self.assertEqual(opencode_executor.execution_timeout(False),900)

class TeachingLibraryAPITests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def test_optional_learning_saves_original_message_and_persists_provenance(self):
  status,snap=self.h.call(self.h.path+'/teaching/resources',{'lesson_id':'L09','choice':'learn'})
  self.assertEqual(status,202);t=self.h.wait()
  self.assertEqual(t['workflow']['teaching_resources']['focus_lesson_id'],'L09')
  self.assertTrue(any('我想结合当前项目了解' in m['content'] for m in t['messages'] if m['role']=='user'))
  trace=t['teaching']['turns'][-1]['teaching_library'];self.assertEqual(trace['lesson_ids'][0],'L09');self.assertFalse(trace['submitted_to_model'])
  status,snap=self.h.call(self.h.path+'/teaching/resources',{'lesson_id':'L09','choice':'later'})
  self.assertEqual(status,200);self.assertIn('L09',snap['teaching_library']['preferences']['deferred_lesson_ids'])
  self.assertIsNone(snap['teaching_library']['preferences']['focus_lesson_id'])
 def test_invalid_lesson_does_not_mutate_task(self):
  before=b.load(self.h.task['id'])
  self.assertEqual(self.h.call(self.h.path+'/teaching/resources',{'lesson_id':'../secret','choice':'learn'})[0],400)
  self.assertEqual(b.load(self.h.task['id']),before)
