import importlib.util
import json
import tempfile
import threading
import unittest
import sys
import time
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('workbench_backend',Path(__file__).resolve().parents[1]/'backend.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BackendTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();b.DATA=Path(cls.temp.name);b.DB=b.DATA/'records.sqlite3'
  cls.server=b.ThreadingHTTPServer(('127.0.0.1',0),b.Handler)
  threading.Thread(target=cls.server.serve_forever,daemon=True).start()
  cls.base='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):
  cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
 def call(self,path,body=None):
  r=Request(self.base+'/api'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
  with urlopen(r) as res:data=json.load(res)
  if isinstance(data,dict) and data.get('teaching_run',{}).get('status') in ('queued','running'):
   for _ in range(100):
    time.sleep(.01)
    with urlopen(self.base+'/api/tasks/'+data['id']) as res:data=json.load(res)
    if data['teaching_run']['status'] not in ('queued','running'):break
  return data
 def test_persistence_confirmation_steps_and_files(self):
  t=self.call('/tasks',{});path='/tasks/'+t['id']
  t=self.call(path+'/plan',{'message':'我想开发待办网站'})
  self.assertEqual(t['step'],0)
  self.assertEqual(t['plan'],[])
  self.assertTrue(t['plan_draft'])
  with self.assertRaises(HTTPError):self.call(path+'/steps/run',{'expected_step':0})
  with self.assertRaises(HTTPError):self.call(path+'/steps/run',{'confirmed':True,'expected_step':0,'instruction':'不确认计划直接执行'})
  t=self.call(path+'/plan/confirm',{'confirmed':True,'plan':t['plan_draft']})
  for step in range(3):
   t=self.call(path+'/steps/run',{'confirmed':True,'expected_step':step,'instruction':'执行当前步骤'})
   self.assertEqual(t['step'],step+1);self.assertEqual(t['stage'],'review')
  with self.assertRaises(HTTPError):self.call(path+'/steps/run',{'confirmed':True,'expected_step':0,'instruction':'重复'})
  t=self.call(path+'/verify',{});self.assertTrue(all(c['pass'] for c in t['checks']))
  t=self.call(path+'/teaching/messages',{'message':'我来检查边界'})
  restored=self.call(path);self.assertEqual(restored['messages'],t['messages']);self.assertIn('localStorage',restored['files']['app.js'])
  self.call(path+'/files',{'path':'app.js','content':'// student edit'})
  self.assertEqual(self.call(path)['files']['app.js'],'// student edit')
  with self.assertRaises(HTTPError):self.call(path+'/files',{'path':'../outside.txt','content':'bad'})
  with urlopen(self.base+'/preview/'+t['id']+'/index.html') as res:self.assertIn(b'<form',res.read())

 def test_teaching_fixture_and_upgrade_denial(self):
  t=self.call('/tasks',{'scenario':'teaching'});path='/tasks/'+t['id']
  self.assertEqual(t['task_definition_id'],'todo-empty-input-validation')
  self.assertEqual(t['strategy_version_id'],'todo-input-v1')
  self.assertEqual(t['teaching_strategy']['version'],1)
  self.assertEqual(t['step'],2)
  self.assertIn('list.append(li)',t['files']['app.js'])
  self.assertNotIn('localStorage',t['files']['app.js'])
  t=self.call(path+'/teaching/review',{})
  self.assertIn('plan',t['teaching'])
  with self.assertRaises(HTTPError):self.call(path+'/teaching/transfer',{'message':'我懂了'})
  with self.assertRaises(HTTPError):self.call(path+'/upgrade-proposals',{'confirmed':True})

 def test_strategy_registry_and_teaching_events_are_persisted_once(self):
  t=self.call('/tasks',{'scenario':'teaching'});stored=b.load(t['id']);s=stored['teaching']
  self.assertEqual(s['phase'],'observe')
  strategies=self.call('/strategies')
  strategy=next(item for item in strategies if item['id']=='todo-input-v1')
  self.assertEqual(strategy['status'],'active')
  self.assertEqual(len(strategy['content_hash']),64)
  b.message(stored,'teaching','user','空格似乎也被添加了')
  s['turns'].append({'id':0,'strategy_version_id':'todo-input-v1','created_at':time.time(),'result':{'assessment':'developing'}})
  s['transfer_answer']={'id':'transfer-test-1','message_id':len(stored['messages']),'answer':'昵称只输入空格时不应创建昵称。','created_at':time.time()}
  b.save(stored);b.save(stored)
  with b.connection() as c:
   session=c.execute('SELECT task_definition_id,task_definition_version,strategy_version_id FROM teaching_sessions WHERE session_id=?',(t['id'],)).fetchone()
   events=c.execute('SELECT event_type,strategy_version_id FROM teaching_events WHERE session_id=? ORDER BY event_type',(t['id'],)).fetchall()
  self.assertEqual(session,('todo-empty-input-validation',1,'todo-input-v1'))
  self.assertEqual(sorted(events),[('student_message','todo-input-v1'),('teaching_turn','todo-input-v1'),('transfer_answer','todo-input-v1')])

 def test_send_acknowledges_before_model_finishes(self):
  t=self.call('/tasks',{});release=threading.Event();entered=threading.Event()
  def slow(*args):entered.set();release.wait(3);return '完成回复'
  with patch.object(b.teaching,'run',side_effect=slow):
   req=Request(self.base+'/api/tasks/'+t['id']+'/teaching/messages',data=json.dumps({'message':'现在到哪一步了'}).encode(),headers={'Content-Type':'application/json'})
   try:
    with urlopen(req,timeout=1) as res:
     self.assertEqual(res.status,202);ack=json.load(res)
    self.assertTrue(entered.wait(1));self.assertEqual(ack['messages'][-1]['content'],'现在到哪一步了')
    with urlopen(self.base+'/api/tasks/'+t['id'],timeout=1) as res:self.assertIn(json.load(res)['teaching_run']['status'],('queued','running'))
   finally:release.set()
   for _ in range(100):
    with urlopen(self.base+'/api/tasks/'+t['id']) as res:done=json.load(res)
    if done['teaching_run']['status']=='completed':break
    time.sleep(.01)
   self.assertEqual(done['messages'][-1]['content'],'完成回复')

 def test_optional_knowledge_can_be_deferred_without_blocking_plan(self):
  t=self.call('/tasks',{});path='/tasks/'+t['id']
  self.assertEqual(t['plan'],[]);self.assertEqual(t['plan_draft'],[])
  t=self.call(path+'/teaching/knowledge',{'topic':'events','choice':'later'})
  self.assertEqual(t['teaching']['course']['knowledge_preferences']['events'],'later')
  t=self.call(path+'/plan',{'message':'先做最小待办'})
  t=self.call(path+'/plan/confirm',{'confirmed':True,'plan':t['plan_draft']})
  self.assertTrue(t['plan'])

 def test_stale_worker_preserves_new_records_and_assessment(self):
  t=self.call('/tasks',{});entered=threading.Event();release=threading.Event()
  def slow(work,action,progress):
   entered.set();release.wait(3);progress('thinking','进度更新不得覆盖记录');return '过期回复'
  with patch.object(b.teaching,'run',side_effect=slow):
   request=Request(self.base+'/api/tasks/'+t['id']+'/teaching/messages',data=b'{"message":"test"}',headers={'Content-Type':'application/json'})
   with urlopen(request) as res:json.load(res)
   self.assertTrue(entered.wait(1))
   try:
    with self.assertRaises(HTTPError):self.call('/tasks/'+t['id']+'/files',{'path':'app.js','content':'API must reject while running'})
    with b.task_lock(t['id']):
     fresh=b.load(t['id']);fresh['changes'].append({'file':'app.js','instruction':'new record'})
     fresh['messages'].append({'role':'user','channel':'teaching','content':'新增证据'})
     fresh['teaching']['assessment']='insufficient';b.save(fresh)
   finally:release.set()
   for _ in range(100):
    done=b.load(t['id'])
    if done['teaching_run']['status']=='failed':break
    time.sleep(.01)
  self.assertEqual(done['changes'][-1]['instruction'],'new record')
  self.assertEqual(done['messages'][-1]['content'],'新增证据')
  self.assertEqual(done['teaching_run']['error'],'stale_context')
  self.assertEqual(done['teaching']['assessment'],'insufficient')

 def test_external_code_change_invalidates_inflight_analysis(self):
  t=self.call('/tasks',{});entered=threading.Event();release=threading.Event()
  def slow(*args):entered.set();release.wait(3);return 'outdated code review'
  with patch.object(b.teaching,'run',side_effect=slow):
   req=Request(self.base+'/api/tasks/'+t['id']+'/teaching/messages',data=b'{"message":"review"}',headers={'Content-Type':'application/json'})
   with urlopen(req) as res:json.load(res)
   self.assertTrue(entered.wait(1))
   try:b.project(t['id']).joinpath('app.js').write_text('// external edit',encoding='utf-8')
   finally:release.set()
   for _ in range(100):
    done=b.load(t['id'])
    if done['teaching_run']['status']=='failed':break
    time.sleep(.01)
  self.assertEqual(done['teaching_run']['error'],'stale_context')
  self.assertFalse(any(m['content']=='outdated code review' for m in done['messages']))
  self.assertEqual(b.project(t['id']).joinpath('app.js').read_text(encoding='utf-8'),'// external edit')

 def test_file_failures_return_json_instead_of_disconnecting(self):
  t=self.call('/tasks',{});path='/tasks/'+t['id']
  b.project(t['id']).joinpath('app.js').write_bytes(b'\xff\xfe')
  with self.assertRaises(HTTPError) as caught:self.call(path)
  self.assertEqual(caught.exception.code,422);self.assertIn('UTF-8',json.load(caught.exception)['error'])
  with patch.object(Path,'read_text',side_effect=PermissionError('test')):
   with self.assertRaises(HTTPError) as caught:self.call(path)
  self.assertEqual(caught.exception.code,500);self.assertIn('error',json.load(caught.exception))

 def test_preview_port_falls_back_when_occupied(self):
  import socket
  with socket.socket() as occupied:
   occupied.bind(('127.0.0.1',0));occupied.listen();port=occupied.getsockname()[1]
   server=b.create_preview_server(port)
   try:self.assertNotEqual(server.server_port,port)
   finally:server.server_close()

 def test_archive_retains_old_records_and_context_is_bounded(self):
  t=self.call('/tasks',{});s=b.teaching.state(t)
  s['turns']=[{'id':i} for i in range(100)]
  s['course']['checkpoints']=[{'turn':i,'goal':'test'} for i in range(100)]
  b.save(t);fresh=b.load(t['id'])
  self.assertEqual(len(fresh['teaching']['turns']),20)
  self.assertEqual(len(fresh['teaching']['course']['checkpoints']),40)
  with b.connection() as c:
   count=c.execute('SELECT COUNT(*) FROM teaching_history WHERE task_id=?',(t['id'],)).fetchone()[0]
  self.assertEqual(count,140)
  ctx=b.teaching.context(b.snapshot(fresh),'review')
  self.assertEqual(len(ctx['course']['checkpoints']),8)
  self.assertEqual(fresh['teaching']['turns'][-1]['id'],99)

 def test_step_type_error_is_explicit(self):
  t=self.call('/tasks',{'scenario':'teaching'})
  with self.assertRaises(HTTPError) as caught:self.call('/tasks/'+t['id']+'/steps/run',{'confirmed':True,'expected_step':'2','instruction':'test'})
  self.assertIn('必须是整数',json.load(caught.exception)['error'])

 def test_failed_file_replace_keeps_original(self):
  t=self.call('/tasks',{});path=b.project(t['id'])/'app.js';original=path.read_text(encoding='utf-8')
  with patch.object(b.os,'replace',side_effect=PermissionError('test')):
   with self.assertRaises(HTTPError) as caught:self.call('/tasks/'+t['id']+'/files',{'path':'app.js','content':'replacement'})
  self.assertEqual(caught.exception.code,500)
  self.assertEqual(path.read_text(encoding='utf-8'),original)
  self.assertEqual(b.load(t['id'])['changes'],[])

 def test_replaced_job_is_not_overwritten_by_old_worker(self):
  t=self.call('/tasks',{});entered=threading.Event();release=threading.Event();finished=threading.Event()
  def slow(*args):entered.set();release.wait(3);finished.set();return 'old result'
  with patch.object(b.teaching,'run',side_effect=slow):
   req=Request(self.base+'/api/tasks/'+t['id']+'/teaching/messages',data=b'{"message":"test"}',headers={'Content-Type':'application/json'})
   with urlopen(req) as res:json.load(res)
   self.assertTrue(entered.wait(1))
   try:
    with b.task_lock(t['id']):
     fresh=b.load(t['id']);fresh['teaching_run']={'id':'new-owner','status':'completed','detail':'new result'};b.save(fresh)
   finally:release.set()
   self.assertTrue(finished.wait(1));time.sleep(.05)
  fresh=b.load(t['id']);self.assertEqual(fresh['teaching_run']['id'],'new-owner')
  self.assertFalse(any(m['content']=='old result' for m in fresh['messages']))

if __name__=='__main__': unittest.main()
