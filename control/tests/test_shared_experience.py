import copy,json,os,sqlite3,tempfile,time,unittest
from unittest.mock import patch
from pathlib import Path
import backend as b
from agents import experience_library as lib,experience_evidence as ev,teaching_evolution as e,teaching
import test_teaching_evolution as old
import test_checkpoints as fixture


def evaluation(review):
 rows=[]
 for dim in review['rubric']['dimensions']:
  items=[]
  for i,rule in enumerate(dim['items']):
   value=(1 if i==0 else .5) if dim['id']=='understanding' else None
   items.append({'id':rule['id'],'value':value,'reason':'解释正确，预测需要提示' if value is not None else '没有对应表现',
    'evidence_ids':['m:2'] if value is not None else [],'quotes':[{'message_id':2,'quote':'状态保存分数，点击会改变分数。'}] if value is not None else []})
  rows.append({'dimension':dim['id'],'reason':'按本轮表现逐项评分','items':items})
 return {'observations':rows,'feedback':[]}


def analyzed(review):
 reflection=old.reflection();reflection['operations'][0]['dimension_ids']=['understanding']
 return {'evaluation':evaluation(review),'reflection':reflection,'provider':{'mode':'model','model':'fixture'}}


class LibraryTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.addCleanup(self.c.close);self.c.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,body TEXT)')
  self.t=old.task();self.t.update(title='计分项目',changes=[],behavior_records=[])
  self.c.execute('INSERT INTO tasks VALUES (?,?)',(self.t['id'],json.dumps(self.t)))
  lib.attach(self.c,self.t);self.base_revision=lib.read(self.c)['revision'];self.review=ev.enrich(self.t,e.build_review(self.t))
 def commit(self):return lib.commit_review(self.c,self.t,self.review,analyzed(self.review))
 def test_formula_and_missing(self):
  v=e.validate_evaluation(evaluation(self.review),self.review);scores=e.scores(v)
  self.assertEqual(scores[0]['score'],75);self.assertEqual(scores[0]['count'],2)
  self.assertTrue(all(s['score'] is None for s in scores[1:]));self.assertEqual(len(v['observations'][0]['items']),2)
 def test_fabricated_and_teacher_only_evidence_rejected(self):
  for mode in ('id','quote','teacher','old'):
   v=evaluation(self.review);item=v['observations'][0]['items'][0];review=copy.deepcopy(self.review)
   if mode=='id':item['evidence_ids']=['test:999']
   if mode=='quote':item['quotes'][0]['quote']='伪造原话'
   if mode=='teacher':item.update(evidence_ids=['m:1'],quotes=[{'message_id':1,'quote':'先看例子'}])
   if mode=='old':review['new_message_ids']=[0]
   with self.subTest(mode=mode),self.assertRaises(ValueError):e.validate_evaluation(v,review)
 def test_artifact_required_for_project_score(self):
  v=evaluation(self.review);item=v['observations'][3]['items'][1];item.update(value=1,evidence_ids=['m:2'],quotes=[{'message_id':2,'quote':'状态保存分数'}])
  with self.assertRaises(ValueError):e.validate_evaluation(v,self.review)
  self.t['changes']=[{'file':'game.js','before':'score=0','after':'score=1'}];self.t['files']={'game.js':'score=1'};review=ev.enrich(self.t,e.build_review(self.t));item['evidence_ids'].append('change:0')
  self.assertEqual(e.validate_evaluation(v,review)['observations'][3]['value'],1)
 def test_stale_artifact_cannot_get_full_project_score(self):
  self.t.update(project_hash='new',execution_records=[{'hash':'old','passed':True}]);review=ev.enrich(self.t,e.build_review(self.t));v=evaluation(review)
  v['observations'][3]['items'][1].update(value=1,evidence_ids=['m:2','test:0'],quotes=[{'message_id':2,'quote':'状态保存分数'}])
  with self.assertRaises(ValueError):e.validate_evaluation(v,review)
 def test_invalid_reflection_no_partial_commit(self):
  before=lib.read(self.c);result=analyzed(self.review);del result['reflection']['operations'][0]['dimension_ids']
  with self.assertRaises(ValueError):lib.commit_review(self.c,self.t,self.review,result)
  self.assertEqual(lib.read(self.c),before)
 def test_cross_project_trial_and_local_cursor(self):
  batch=self.commit();entry=lib.read(self.c)['entries'][-1]
  other=old.task();other['id']='second';other['teaching_evolution']['cursor']=-1;lib.attach(self.c,other)
  self.assertIn(entry['id'],[r['id'] for r in e.packet(other)['entries']])
  self.assertEqual(other['teaching_evolution']['cursor'],-1);self.assertEqual(other['teaching_evolution']['reviews'],[])
  self.assertEqual(entry['source_project'],self.t['id']);self.assertEqual(entry['status'],'trial');self.assertTrue(batch['evidence'])
 def test_undo_preserves_scores_messages_and_cursor(self):
  before=copy.deepcopy(self.t['messages']);batch=self.commit();target=lib.read(self.c)['entries'][-1]['id']
  restored=lib.manage(self.c,{'expected_revision':self.base_revision+1,'action':'undo','batch_id':batch['id']})
  lib.attach(self.c,self.t);self.assertNotIn(target,[r['id'] for r in e.packet(self.t)['entries']])
  self.assertEqual(self.t['messages'],before);self.assertEqual(self.t['teaching_evolution']['cursor'],2)
  self.assertEqual(next(b for b in restored['batches'] if b.get('review'))['review']['scores'][0]['score'],75)
  with self.assertRaises(ValueError):lib.manage(self.c,{'expected_revision':self.base_revision+2,'action':'undo','batch_id':batch['id']})
 def test_undo_item_and_no_match(self):
  batch=self.commit();target=lib.read(self.c)['entries'][-1]['id'];other=old.task();other['plan']=[];other['messages']=[{'role':'user','channel':'teaching','content':'网页颜色'}];lib.attach(self.c,other)
  self.assertNotIn(target,[r['id'] for r in e.packet(other)['entries']])
  restored=lib.manage(self.c,{'expected_revision':self.base_revision+1,'action':'undo','batch_id':batch['id'],'entry_id':target})
  self.assertTrue(next(b for b in restored['batches'] if b['id']==batch['id'])['changes'][-1]['undone'])
 def test_conflict_does_not_override_later_edits(self):
  batch=self.commit();target=lib.read(self.c)['entries'][-1]['id']
  lib.manage(self.c,{'expected_revision':self.base_revision+1,'action':'status','entry_id':target,'status':'inactive'});before=lib.read(self.c)
  for revision in (self.base_revision+1,self.base_revision+2):
   with self.assertRaises(ValueError):lib.manage(self.c,{'expected_revision':revision,'action':'undo','batch_id':batch['id']})
  self.assertEqual(lib.read(self.c),before)
  with self.assertRaises(ValueError):lib.commit_review(self.c,self.t,self.review,analyzed(self.review))
 def test_unseen_matching_trial_has_priority_over_observed_one(self):
  self.commit();lib.attach(self.c,self.t);state=e.state(self.t);experienced=state['entries'][-1]
  candidate=copy.deepcopy(experienced);candidate.update(id='new-pending',tags=['状态'],helpful=0)
  experienced.update(tags=['状态','计分'],helpful=3)
  state['entries'].append(candidate);state['trial_observations']={experienced['id']:{'provided_count':4,'helpful':3},candidate['id']:{'provided_count':0}}
  packet=e.packet(self.t);trials=[r for r in packet['entries'] if r['status']=='trial']
  self.assertEqual([r['id'] for r in trials],['new-pending'])
  self.assertEqual(packet['validation_focus']['entry_id'],'new-pending')
  self.assertEqual(packet['validation_focus']['observe'],candidate['verify'])
  candidate['tags']=['无关的网络部署'];self.assertNotIn('new-pending',[r['id'] for r in e.packet(self.t)['entries']])
 def test_provided_state_is_shared_but_not_effectiveness(self):
  self.commit();book=lib.read(self.c);entry=book['entries'][-1]
  self.assertEqual(lib.trial_observations(self.c,book)[entry['id']]['stage'],'pending')
  self.t['teaching_evolution']['loads'].append({'reply_message_id':1,'entries':[{'id':entry['id'],'revision':entry['revision']}],'adoption_verified':False})
  self.c.execute('UPDATE tasks SET body=? WHERE id=?',(json.dumps(self.t),self.t['id']))
  observed=lib.trial_observations(self.c,book)[entry['id']]
  self.assertEqual(observed['stage'],'awaiting_evidence');self.assertEqual(observed['provided_count'],1)
  self.assertFalse(book['entries'][-1]['verified'])
  book['reviews'].append({'evaluation':{'feedback':[{'entry_id':entry['id'],'entry_revision':entry['revision'],'outcome':'helpful'}]}})
  self.assertEqual(lib.trial_observations(self.c,book)[entry['id']]['stage'],'positive_observation')
  self.assertEqual(book['entries'][-1]['status'],'trial');self.assertFalse(book['entries'][-1]['verified'])
 def test_reflection_revises_same_id_and_undo_restores_content(self):
  target=self.review['entries'][0];original=copy.deepcopy(next(x for x in lib.read(self.c)['entries'] if x['id']==target['id']))
  result=analyzed(self.review);result['reflection']['operations'][0].update(type='revise',target_id=target['id'])
  batch=lib.commit_review(self.c,self.t,self.review,result);book=lib.read(self.c);changed=next(x for x in book['entries'] if x['id']==target['id'])
  self.assertEqual(len(book['entries']),15);self.assertEqual(changed['revision'],original['revision']+1)
  self.assertEqual(changed['status'],'trial');self.assertEqual(changed['origin'],'reflection');self.assertFalse(changed['verified'])
  self.assertEqual(changed['history'][-1]['action'],original['action']);self.assertEqual(batch['review']['changes'][0]['type'],'revise')
  restored=lib.manage(self.c,{'expected_revision':book['revision'],'action':'undo','batch_id':batch['id']})
  self.assertEqual(next(x for x in restored['entries'] if x['id']==target['id'])['action'],original['action'])
 def test_reflection_can_retire_initial_strategy_without_erasing_it(self):
  target=self.review['entries'][0];result=analyzed(self.review);result['reflection']['operations'][0].update(type='deactivate',target_id=target['id'])
  batch=lib.commit_review(self.c,self.t,self.review,result);book=lib.read(self.c);entry=next(x for x in book['entries'] if x['id']==target['id'])
  self.assertEqual(len(book['entries']),15);self.assertEqual(entry['status'],'inactive');self.assertTrue(entry['stop_quotes'])
  self.assertEqual(batch['review']['changes'][0]['type'],'deactivate');self.assertTrue(entry['history'])
  lib.attach(self.c,self.t)
  self.assertNotIn(entry['id'],[x['id'] for x in e.packet(self.t)['entries']])
  restored=lib.manage(self.c,{'expected_revision':book['revision'],'action':'undo','batch_id':batch['id']})
  self.assertEqual(next(x for x in restored['entries'] if x['id']==target['id'])['status'],target['status'])
 def test_empty_operations_keep_entries_and_preserve_evaluation(self):
  before=copy.deepcopy(lib.read(self.c)['entries']);result=analyzed(self.review);result['reflection']['operations']=[]
  batch=lib.commit_review(self.c,self.t,self.review,result)
  self.assertEqual(lib.read(self.c)['entries'],before);self.assertEqual(batch['changes'],[]);self.assertTrue(batch['review']['evaluation'])
 def test_off_restore_keep_audit(self):
  self.commit();lib.manage(self.c,{'expected_revision':self.base_revision+1,'action':'options','mode':'off','auto':False});lib.attach(self.c,self.t)
  self.assertEqual(e.packet(self.t)['entries'],[])
  restored=lib.manage(self.c,{'expected_revision':self.base_revision+2,'action':'restore','target_revision':0})
  self.assertEqual(restored['mode'],'observe');self.assertFalse(restored['auto']);self.assertTrue(next(b for b in restored['batches'] if b.get('review'))['review'])


class LibraryHTTPTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def test_real_async_evaluate_reflect_next_project_and_undo(self):
  t=b.load(self.h.task['id']);t['messages']=old.task()['messages'];t['changes']=[];b.save(t);calls=[]
  def model(config,system,value):
   calls.append((system,copy.deepcopy(value)))
   return evaluation(value) if '独立教学证据评价器' in system else analyzed(value['episode'])['reflection']
  with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'call_model',side_effect=model):
   code,_=self.h.call(self.h.path+'/teaching/experience-review',{});self.assertEqual(code,202)
   for _ in range(300):
    t=b.load(t['id'])
    if t['teaching_evolution']['run']['status']!='running':break
    time.sleep(.01)
   self.assertEqual(t['teaching_evolution']['run']['status'],'completed',t['teaching_evolution']['run'])
  self.assertEqual(len(calls),2);self.assertEqual(calls[1][1]['evaluation']['observations'][0]['value'],.75)
  book=self.h.call('/api/experience-library')[1];self.assertEqual(next(b for b in book['batches'] if b.get('review'))['review']['scores'][0]['score'],75)
  new=self.h.call('/api/tasks',{'coding_mode':'opencode'})[1];new['messages'].append({'role':'user','channel':'teaching','content':'计分状态是什么'});new['files']={};seen=[]
  with patch.dict(os.environ,{'TEACHING_MODE':'sample'}),patch.object(teaching,'project_chat',side_effect=lambda agent,ctx,progress:seen.append(ctx['experience_context']) or '测试教学'):
   teaching.run(new)
  target=book['entries'][-1]['id'];self.assertIn(target,[x['id'] for x in seen[0]['entries']])
  messages=copy.deepcopy(t['messages']);code,undo=self.h.call('/api/experience-library',{'expected_revision':book['revision'],'action':'undo','batch_id':next(b for b in book['batches'] if b.get('review'))['id']})
  self.assertEqual(code,200);self.assertEqual(b.load(t['id'])['messages'],messages)
  other=self.h.call('/api/tasks/'+new['id'])[1];self.assertNotIn(target,[x['id'] for x in e.packet(other)['entries']])

class EvaluationRepairTests(unittest.TestCase):
 def test_one_bounded_repair_preserves_strict_evidence_checks(self):
  task=old.task();review=ev.enrich(task,e.build_review(task));bad=evaluation(review);bad['observations'][0]['items'][0]['id']='wrong-item'
  answers=[bad,evaluation(review),analyzed(review)['reflection']];calls=[]
  def model(config,system,value):calls.append(copy.deepcopy(value));return answers[len(calls)-1]
  with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'call_model',side_effect=model):result=e.analyze(task,review)
  self.assertEqual(len(calls),3);self.assertIn('format_repair',calls[1]);self.assertEqual(result['scores'][0]['score'],75)
 def test_bad_repair_fails_instead_of_writing_invalid_scores(self):
  task=old.task();review=ev.enrich(task,e.build_review(task));bad=evaluation(review);bad['observations'][0]['items'][0]['evidence_ids']=['fabricated']
  with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(e,'call_model',return_value=bad) as send:
   with self.assertRaises(ValueError):e.analyze(task,review)
  self.assertEqual(send.call_count,2)
