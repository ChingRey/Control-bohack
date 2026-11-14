import time
import unittest
from unittest.mock import patch
import test_backend as base
b=base.b

class BridgeApiTests(unittest.TestCase):
 setUpClass=classmethod(base.BackendTest.setUpClass.__func__)
 tearDownClass=classmethod(base.BackendTest.tearDownClass.__func__)
 call=base.BackendTest.call
 def test_pause_poll_resume_next_phase(self):
  task=self.call('/tasks',{'coding_mode':'opencode'});path='/tasks/'+task['id']
  plan=['Create first file','Modify first file']
  self.call(path+'/coding/plan-draft',{'plan':plan})
  self.call(path+'/plan/confirm',{'plan':plan,'confirmed':True})
  config=b.opencode_executor.CONFIG
  b.opencode_executor.configure('test-key','test-model')
  calls=[]
  def execute(files,packet,*args):
   calls.append(packet)
   return {'text':'Saved file','files':{'probe.js':str(len(calls))},'events':[]}
  def wait():
   for _ in range(150):
    t=self.call(path)
    if t.get('coding_run',{}).get('status')!='running':return t
    time.sleep(.01)
   self.fail('Execution timed out')
  try:
   with patch.object(b.opencode_executor,'binary',return_value='opencode'),patch.object(b.opencode_executor,'execute',side_effect=execute):
    self.call(path+'/steps/run',{'confirmed':True,'expected_step':0,'instruction':plan[0]})
    first=wait();self.assertEqual(first['step'],0)
    event=self.call(path+'/bridge/events')['events'][0]
    unlock={'checkpoint_id':event['checkpoint_id'],'request_id':'unlock-1','action':'skill_unlock','skill_id':'future-skill','version':'1','teacher_decision_id':'lesson-decision-1'}
    receipt=self.call(path+'/bridge/commands',unlock)
    self.assertEqual(receipt['status'],'pending_catalog');self.assertFalse(receipt['applied'])
    self.assertEqual(self.call(path+'/bridge/commands',unlock),receipt)
    skills=self.call(path+'/bridge/skills')
    self.assertEqual(skills['catalog'],[]);self.assertEqual(len(skills['decisions']),1)
    self.assertEqual(event['project_evidence']['changes'][0]['file'],'probe.js')
    self.assertEqual(self.call(path+'/bridge/files')['files']['probe.js'],'1')
    request={'checkpoint_id':event['checkpoint_id'],'request_id':'resume-1','action':'resume'}
    self.call(path+'/bridge/commands',request)
    second=wait();self.assertEqual(second['step'],1)
    self.call(path+'/bridge/commands',request)
    self.assertEqual(len(calls),2)
    self.assertEqual(len(self.call(path+'/bridge/events')['events']),2)
  finally:b.opencode_executor.CONFIG=config
