import copy
import io
import json
import os
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import backend as b
from agents import workflow, workflow_records as wr, project_safety, project_delivery, student_library, project_runner, browser_runner
import test_checkpoints as fixture

class FullWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def wait_all(self):
  for _ in range(1000):
   with b.task_lock(self.h.task['id']):t=b.load(self.h.task['id'])
   if not b.task_busy(t) and not any(m.get('queue_status')=='queued' for m in t['messages']):return t
   time.sleep(.01)
  self.fail('background task did not finish')
 def proposal(self,kind='rule',content='Keep existing data during UI changes'):
  return {'kind':kind,'content':content,'title':'Preserve data','when':'Changing presentation','limits':'Schema migrations need a separate design','evidence_ids':[0],'quotes':[{'message_id':0,'quote':'Preserve existing data'}]}
 def seed(self):
  t=b.load(self.h.task['id']);t['messages'][0]['content']='Preserve existing data';wr.initialize(t);return t
 def test_queue_survives_busy_and_is_idempotent_without_staling_files(self):
  entered=threading.Event();release=threading.Event();calls=[]
  def execute(files,packet,planning=False,chatting=False):
   calls.append(packet.get('student_message',packet.get('instruction')))
   if len(calls)==1:entered.set();release.wait(4)
   return {'text':'Written','files':{**files,'src/run'+str(len(calls))+'.js':'ready'},'events':[]}
  self.addCleanup(release.set)
  with patch.object(b.opencode_executor,'execute',side_effect=execute):
   one={'channel':'coding','message':'创建第一个代码文件','request_id':'q1'}
   self.assertEqual(self.h.call(self.h.path+'/chat/send',one)[0],202);self.assertTrue(entered.wait(2))
   two={'channel':'coding','message':'创建第二个代码文件','request_id':'q2'}
   self.assertEqual(self.h.call(self.h.path+'/chat/send',two)[0],202)
   self.assertEqual(self.h.call(self.h.path+'/chat/send',two)[0],202)
   self.assertEqual(self.h.call(self.h.path+'/chat/send',{**two,'message':'different'})[0],400)
   release.set();t=self.wait_all()
  self.assertEqual(len(calls),2);self.assertEqual(t['coding_run']['status'],'completed')
  self.assertTrue({'src/run1.js','src/run2.js'}<=set(b.read_project_files(t['id'])))
  self.assertEqual(len([m for m in t['messages'] if m.get('request_id')=='q2']),1)
 def test_restart_requires_retry_and_preserves_queued_message(self):
  t=self.seed();t['messages'].append({'channel':'coding','role':'user','content':'create','request_id':'queued','queue_status':'queued'})
  self.assertTrue(b.recover_interrupted(t));self.assertEqual(t['messages'][-1]['queue_status'],'needs_retry')
 def test_bad_extraction_has_no_partial_effect(self):
  t=self.seed();before=copy.deepcopy(t)
  bad=self.proposal();bad['quotes'][0]['quote']='not in source'
  with self.assertRaises(ValueError):wr.candidates(t,{'items':[self.proposal(),bad]},[0])
  self.assertEqual(t,before)
 def test_rules_revise_disable_and_cap_without_losing_history(self):
  t=self.seed();row=wr.candidates(t,{'items':[self.proposal()]},[0])[0]
  wr.review(t,{'proposal_id':row['id'],'decision':'accept','expected_revision':0})
  rule=t['workflow']['rules'][0]
  replacement=self.proposal(content='Keep data and storage keys unchanged');replacement['replaces_id']=rule['id']
  row2=wr.candidates(t,{'items':[replacement]},[0])[0]
  wr.review(t,{'proposal_id':row2['id'],'decision':'accept','expected_revision':1})
  self.assertEqual(len(t['workflow']['rules']),1);self.assertEqual(rule['revision'],2);self.assertEqual(len(rule['history']),1)
  self.assertFalse(rule['verified'])
  wr.rule_status(t,{'rule_id':rule['id'],'status':'inactive','expected_revision':2});self.assertEqual(wr.active_rules(t),[])
  wr.rule_status(t,{'rule_id':rule['id'],'status':'active','expected_revision':3})
  for i in range(14):
   row=wr.candidates(t,{'items':[self.proposal(content='Rule '+str(i))]},[0])[0]
   wr.review(t,{'proposal_id':row['id'],'decision':'accept','expected_revision':t['workflow']['revision']})
  row=wr.candidates(t,{'items':[self.proposal(content='one too many')]},[0])[0]
  with self.assertRaises(ValueError):wr.review(t,{'proposal_id':row['id'],'decision':'accept','expected_revision':t['workflow']['revision']})
  self.assertEqual(len(wr.active_rules(t)),15)
 def test_local_library_explicit_and_project_scoped(self):
  t=self.seed();row=wr.candidates(t,{'items':[self.proposal()]},[0])[0];wr.review(t,{'proposal_id':row['id'],'decision':'accept','expected_revision':0})
  with b.connection() as conn:
   alice=student_library.create(conn,'Alice');bob=student_library.create(conn,'Bob')
   student_library.attach(conn,t,{'student_id':alice['id'],'confirmed':True})
   student_library.promote(conn,t,{'confirmed':True,'rule_ids':[t['workflow']['rules'][0]['id']],'include_profile':True})
   new={'workflow':workflow.state({})};self.assertEqual(wr.active_rules(new),[])
   student_library.attach(conn,new,{'student_id':alice['id'],'confirmed':True})
   self.assertEqual(len(wr.active_rules(new)),1)
   other={};student_library.attach(conn,other,{'student_id':bob['id'],'confirmed':True});self.assertEqual(wr.active_rules(other),[])
   student_library.attach(conn,new,{'student_id':alice['id'],'confirmed':True});self.assertEqual(len(wr.active_rules(new)),1)
 def test_delivery_excludes_env_and_marks_source_evidence(self):
  t=self.seed();statement={'how_to_run':'Use a static server','tested':'Clicked add','limitations':'Local only'}
  bundle,evidence=project_delivery.build(t,{'index.html':'<h1>Hi</h1>','.env':'PRIVATE=do-not-export','node_modules/x':'excluded'},{},statement)
  with zipfile.ZipFile(io.BytesIO(bundle)) as z:
   self.assertNotIn('project/.env',z.namelist());self.assertNotIn('project/node_modules/x',z.namelist());self.assertIn('HANDOFF.md',z.namelist());self.assertIn('project/index.html',z.namelist())
  self.assertFalse(evidence['safety']['publication_blocked'])
  secret='sk-'+'aB19'*10
  findings=project_safety.scan({'app.js':'const apiKey="'+secret+'";fetch("/api")'})
  self.assertTrue(findings['publication_blocked']);self.assertNotIn(secret,json.dumps(findings))
  with self.assertRaises(ValueError):project_delivery.build(t,{'app.js':'const apiKey="'+secret+'"'}, {},statement)
 def test_actual_python_recipe_and_secret_free_child_environment(self):
  with patch.dict(os.environ,{'TEACHING_API_KEY':'not-inherited','CODING_API_KEY':'not-inherited'}):
   result=project_runner.run({'tests/test_env.py':'import unittest, os\nclass TestEnvironment(unittest.TestCase):\n def test_no_key(self):\n  assert "TEACHING_API_KEY" not in os.environ\n  assert "CODING_API_KEY" not in os.environ\n'}, {},'python-unittest')
  self.assertTrue(result['passed']);self.assertEqual(result['exit_code'],0)
  with self.assertRaises(ValueError):project_runner.run({}, {},'python; delete')
 def test_model_organizer_proposals_are_not_confirmed_or_applied(self):
  t=self.seed();value={'choices':[{'message':{'content':json.dumps({'items':[self.proposal('requirements')]})}}]}
  with patch.dict(os.environ,{'TEACHING_MODE':'model'}),patch.object(wr.providers,'request',return_value=None),patch.object(wr.providers,'normalize',side_effect=lambda c,r:r),patch.object(b.teaching,'request_model',return_value=value):rows=wr.organize(t)
  self.assertEqual(rows[0]['status'],'pending_review');self.assertEqual(t['workflow']['materials']['requirements'],[])

@unittest.skipUnless(os.environ.get('CONTROL_RUN_BROWSER_TESTS')=='1','optional real Chromium acceptance')
class RealBrowserTests(unittest.TestCase):
 def test_real_browser_positive_negative_and_reload(self):
  files={'index.html':'<!doctype html><body><input id="v"><button id="add">add</button><ul id="list"></ul><script>let rows=JSON.parse(localStorage.getItem("rows")||"[]");function draw(){list.innerHTML=rows.map(x=>"<li>"+x+"</li>").join("")}add.onclick=()=>{if(v.value.trim()){rows.push(v.value.trim());localStorage.setItem("rows",JSON.stringify(rows));draw()}};draw()</script>'}
  cases=[{'action':'fill','selector':'#v','value':'  '},{'action':'click','selector':'#add'},{'action':'assert_count','selector':'li','count':0},{'action':'fill','selector':'#v','value':'first'},{'action':'click','selector':'#add'},{'action':'reload'},{'action':'assert_text','selector':'li','text':'first'}]
  passed=browser_runner.run(files,{},cases);self.assertTrue(passed['passed']);self.assertEqual(passed['source'],'real_chromium_browser')
  failed=browser_runner.run(files,{},[{'action':'assert_count','selector':'li','count':5}]);self.assertFalse(failed['passed'])


class MoreWorkflowChecks(unittest.TestCase):
 def test_runtime_really_serves_and_does_not_inherit_provider_key(self):
  from agents import project_runtime
  from urllib.request import urlopen
  files={'server.py':'import os\nfrom http.server import HTTPServer,BaseHTTPRequestHandler\nassert "TEACHING_API_KEY" not in os.environ\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(b"runtime-ready")\nHTTPServer(("127.0.0.1",int(os.environ["PORT"])),H).serve_forever()\n'}
  self.addCleanup(project_runtime.stop,'runtime-test')
  with patch.dict(os.environ,{'TEACHING_API_KEY':'test-private-key'}):status=project_runtime.start('runtime-test',files,{},'python','server.py')
  with urlopen(status['url'],timeout=3) as response:self.assertEqual(response.read(),b'runtime-ready')
  project_runtime.stop('runtime-test');self.assertEqual(project_runtime.status('runtime-test')['status'],'stopped')
 def test_wait_only_browser_and_zero_tests_do_not_pass(self):
  with self.assertRaises(ValueError):browser_runner.validate([{'action':'wait','ms':10}])
  result=project_runner.run({'tests/__init__.py':''},{},'python-unittest');self.assertFalse(result['passed'])
 def test_model_serialized_source_is_redacted_without_editing_original(self):
  secret='sk-'+'aB19'*10;value={'files':{'app.js':'const apiKey="'+secret+'"'}}
  masked=project_safety.scrub([{'content':json.dumps(value)}])
  self.assertNotIn(secret,json.dumps(masked));self.assertIn(secret,value['files']['app.js'])
 def test_feature_accept_needs_current_version_evidence(self):
  t={};s=wr.initialize(t);row=wr.feature(t,{'action':'create','title':'Counter','expected_revision':0},'hash1')
  body={'action':'accept','feature_id':row['id'],'explanation':'The old display remains; counter was checked','expected_revision':s['revision']}
  t['behavior_records']=[{'id':'check','hash':'old-hash','result':'passed'}]
  with self.assertRaises(ValueError):wr.feature(t,body,'hash1')
  t['behavior_records'][0]['hash']='hash1';wr.feature(t,body,'hash1')
  self.assertEqual(row['status'],'accepted');self.assertFalse(row['verified_mastery'])


class QueueFailureChecks(unittest.TestCase):
 def test_failed_model_message_is_saved_and_explicitly_retryable(self):
  h=fixture.CheckpointIntegrationTests();h.setUp();self.addCleanup(h.doCleanups)
  with patch.object(b.opencode_executor,'execute',side_effect=ValueError('fixture model unavailable')):
   status,_=h.call(h.path+'/chat/send',{'channel':'coding','message':'创建文件','request_id':'retry-me'})
   self.assertEqual(status,202)
   for _ in range(100):
    time.sleep(.01);task=b.load(h.task['id']);row=next(m for m in task['messages'] if m.get('request_id')=='retry-me')
    if row.get('queue_status')=='needs_retry':break
  self.assertEqual(row['queue_status'],'needs_retry');self.assertEqual(row['content'],'创建文件')
  def execute(files,*args):return {'text':'written','files':{**files,'new.js':'done'},'events':[]}
  with patch.object(b.opencode_executor,'execute',side_effect=execute):
   self.assertEqual(h.call(h.path+'/chat/retry',{'request_id':'retry-me'})[0],202);task=h.wait()
  self.assertEqual(task['coding_run']['status'],'completed');self.assertEqual(len([m for m in task['messages'] if m.get('request_id')=='retry-me']),1)
