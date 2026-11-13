import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import knowledge, learning, teaching, coding_workflow


class KnowledgeApiTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
  self.data=patch.object(b,'DATA',Path(self.temp.name));self.data.start()
  self.db=patch.object(b,'DB',Path(self.temp.name)/'records.sqlite3');self.db.start()
  self.task=self.call('/api/tasks',{})[1];self.path='/api/tasks/'+self.task['id']

 def tearDown(self):
  self.db.stop();self.data.stop();self.temp.cleanup()

 def call(self,path,body=None):
  handler=b.Handler.__new__(b.Handler);handler.path=path;handler.server=SimpleNamespace(server_port=8772)
  raw=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else b''
  handler.headers={'Host':'127.0.0.1:8772','Content-Length':str(len(raw))};handler.rfile=io.BytesIO(raw)
  result=[];handler.reply=lambda code,obj,*args:result.extend((code,copy.deepcopy(obj)))
  if body is None:handler.do_GET()
  else:handler.do_POST()
  return result

 def test_manual_experience_persists_requires_review_and_respects_toggle(self):
  path=self.path+'/knowledge'
  self.assertEqual(self.call(path+'/manual',{'title':'Whitespace','content':'Trim whitespace'})[0],400)
  status,snapshot=self.call(path+'/manual',{'title':'Whitespace','content':'Trim whitespace before validating input','confirmed':True})
  self.assertEqual(status,200)
  item=snapshot['project_knowledge'][0];kid=item['id']
  self.assertEqual(item['source_turn'],-1)
  self.assertEqual(self.call(path+'/search',{'query':'whitespace'})[1]['items'],[])
  self.assertEqual(self.call(path+'/'+kid+'/review',{'confirmed':True,'decision':'approve','reviewer':'local'})[0],200)
  self.assertEqual(len(self.call(path+'/search',{'query':'whitespace'})[1]['items']),1)
  other=self.call('/api/tasks',{})[1]
  self.assertEqual(self.call('/api/tasks/'+other['id']+'/knowledge/search',{'query':'whitespace'})[1]['items'],[])
  task=b.load(self.task['id']);task['mode']='opencode';b.save(task)
  captured=[]
  def execute(files,payload,*args):
   captured.append(copy.deepcopy(payload))
   return {'text':'Review the whitespace behavior.','files':files,'events':[]}
  import time
  with patch.object(b.opencode_executor,'CONFIG',{'key':'test','model':'test','url':'https://example.invalid'}),patch.object(b.opencode_executor,'binary',return_value='opencode'),patch.object(b.opencode_executor,'execute',side_effect=execute):
   for enabled in (True,False):
    self.assertEqual(self.call(path+'/settings',{'enabled':enabled})[0],200)
    self.assertEqual(self.call(self.path+'/coding/messages',{'message':'Review whitespace input'})[0],202)
    deadline=time.time()+5
    while time.time()<deadline and b.load(self.task['id'])['coding_run']['status']=='running':time.sleep(.01)
    self.assertEqual(b.load(self.task['id'])['coding_run']['status'],'completed')
   self.assertEqual(captured[0]['project_knowledge'][0]['id'],kid)
   self.assertEqual(captured[1]['project_knowledge'],[])
  self.call(path+'/'+kid+'/review',{'confirmed':True,'decision':'withdraw','reviewer':'local'})
  self.assertEqual(self.call(path+'/search',{'query':'whitespace'})[1]['items'],[])
  self.assertEqual(self.call(path+'/'+kid+'/review',{'confirmed':True,'decision':'approve','reviewer':'local'})[0],200)

 def add_candidate(self):
  task=b.load(self.task['id']);task['files']=b.read_project_files(task['id'])
  b.message(task,'teaching','user','输入检查应该先于列表生成，避免留下空白事项。')
  ctx=teaching.context(task,'review')
  update={'knowledge_candidates':[{'type':'verified_pattern','title':'空白输入校验','content':'提交前应去除首尾空白，再检查是否为空。',
      'evidence_ids':[len(task['messages'])-1],'quotes':[{'message_id':len(task['messages'])-1,'quote':'输入检查应该先于列表生成'}]}]}
  learning.apply(task,learning.validate(update,ctx),0,ctx['code_hash']);b.save(task)
  return learning.state(task)['knowledge_candidates'][0]['id']

 def test_candidate_is_pending_until_review_then_searchable_by_same_task(self):
  candidate_id=self.add_candidate();path=f'{self.path}/knowledge'
  self.assertEqual(self.call(path+'/search',{'query':'空白输入'})[1]['items'],[])
  status,reviewed=self.call(path+f'/{candidate_id}/review',{'confirmed':True,'decision':'approve','reviewer':'project-maintainer','note':'已检查来源'})
  self.assertEqual(status,200);self.assertEqual(reviewed['teaching']['learning']['knowledge_candidates'][0]['status'],'approved')
  status,result=self.call(path+'/search',{'query':'空白输入'})
  self.assertEqual(status,200);self.assertEqual(len(result['items']),1)
  self.assertFalse(result['items'][0]['stale_for_code'])
  self.assertEqual(self.call('/api/tasks/'+('0'*8+'-0000-0000-0000-000000000000')+'/knowledge/search',{'query':'空白输入'})[0],400)

 def test_review_requires_confirmation_and_withdrawal_removes_retrieval(self):
  candidate_id=self.add_candidate();path=f'{self.path}/knowledge/{candidate_id}/review'
  self.assertEqual(self.call(path,{'confirmed':False,'decision':'approve','reviewer':'maintainer'})[0],400)
  self.assertEqual(self.call(path,{'confirmed':True,'decision':'approve','reviewer':'maintainer'})[0],200)
  self.assertEqual(self.call(path,{'confirmed':True,'decision':'withdraw','reviewer':'maintainer'})[0],200)
  self.assertEqual(self.call(f'{self.path}/knowledge/search',{'query':'空白输入'})[1]['items'],[])

 def test_backend_coding_run_retrieves_and_logs_approved_knowledge(self):
  candidate_id=self.add_candidate()
  self.call(f'{self.path}/knowledge/{candidate_id}/review',{'confirmed':True,'decision':'approve','reviewer':'maintainer'})
  task=b.load(self.task['id']);task.update(mode='opencode',plan=['实现空白输入校验'],step=0)
  coding_workflow=b.coding_workflow;coding_workflow.confirm(task);b.save(task)
  b.opencode_executor.configure('test-key','qwen-test','cn')
  captured=[]
  original_config=b.opencode_executor.CONFIG
  try:
   with patch.object(b.opencode_executor,'binary',return_value='opencode'), patch.object(b.opencode_executor,'execute',side_effect=lambda files,payload,*a:(captured.append(copy.deepcopy(payload)) or {'text':'已按计划检查。','files':files,'events':[]})):
    status,_=self.call(self.path+'/steps/run',{'confirmed':True,'expected_step':0,'instruction':'请先检查空白输入的约定'})
    self.assertEqual(status,202)
    import time
    deadline=time.time()+5
    while time.time()<deadline:
     with b.task_lock(self.task['id']):current=b.load(self.task['id'])
     if current['coding_run']['status'] not in ('queued','running') and current.get('teaching_run',{}).get('status') not in ('queued','running'):break
     time.sleep(.01)
   current=b.load(self.task['id'])
   self.assertEqual(current['coding_run']['status'],'completed')
   self.assertEqual(captured[0]['project_knowledge'][0]['id'],candidate_id)
   self.assertEqual(current['coding_workflow']['loads'][-1]['knowledge_versions'][0]['id'],candidate_id)
  finally:b.opencode_executor.CONFIG=original_config

 def test_knowledge_is_injected_into_opencode_packet_and_logged_as_reference(self):
  candidate_id=self.add_candidate();review_path=f'{self.path}/knowledge/{candidate_id}/review'
  self.call(review_path,{'confirmed':True,'decision':'approve','reviewer':'maintainer'})
  task=b.load(self.task['id']);task.update(mode='opencode',plan=['检查空白输入'],step=0)
  b.save(task)
  code=knowledge.code_hash(b.read_project_files(task['id']))
  with b.connection() as conn:
   records=knowledge.search(conn,task['id'],'空白输入',code)
  self.assertEqual(len(records),1)
  packet=b.coding_workflow.prepare(task,'检查空白输入',learning.coding_packet(task,'检查空白输入'),records)
  self.assertEqual(packet['project_knowledge'][0]['id'],candidate_id)
  self.assertTrue(packet['project_knowledge'][0]['evidence_ids'])


if __name__=='__main__':unittest.main()
