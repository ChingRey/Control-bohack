import unittest
from agents import teaching_bridge as b, coding_workflow as w

class BridgeTests(unittest.TestCase):
 def task(self):
  t={'id':'session','plan':['create file','edit file'],'step':0,'messages':[]}
  w.confirm(t);w.state(t)['checkpoints'][0]['status']='executed_pending_review'
  b.publish(t,'create file','done',[{'file':'a.js','before':'','after':'42'}],{'a.js':'42'})
  return t
 def test_resume_exactly_once(self):
  t=self.task();e=b.events(t)[0];request={'request_id':'one','checkpoint_id':e['checkpoint_id'],'action':'resume'}
  receipt,instruction=b.command(t,request)
  self.assertEqual(instruction,'edit file');self.assertEqual(t['step'],1)
  repeated,again=b.command(t,request)
  self.assertEqual(receipt,repeated);self.assertIsNone(again);self.assertEqual(t['step'],1)
  with self.assertRaises(ValueError):b.command(t,{**request,'request_id':'another'})
 def test_multiple_revisions_have_new_evidence(self):
  t=self.task();e=b.events(t)[0]
  body={'request_id':'rev','checkpoint_id':e['checkpoint_id'],'action':'modify','instruction':'fix a.js'}
  with self.assertRaises(ValueError):b.command(t,body)
  _,instruction=b.command(t,{**body,'student_confirmed':True})
  self.assertEqual(instruction,'fix a.js');self.assertEqual(t['step'],0)
  b.publish(t,instruction,'fixed',[],{'a.js':'43'})
  latest=b.events(t)[-1];self.assertNotEqual(e['checkpoint_id'],latest['checkpoint_id'])
  b.command(t,{'request_id':'rev2','checkpoint_id':latest['checkpoint_id'],'action':'modify','instruction':'fix again','student_confirmed':True})
 def test_skill_not_falsely_enabled(self):
  t=self.task();e=b.events(t)[0]
  receipt,_=b.command(t,{'request_id':'skill','checkpoint_id':e['checkpoint_id'],'action':'skill_unlock','skill_id':'unknown','version':'1','teacher_decision_id':'decision1'})
  self.assertFalse(receipt['applied']);self.assertEqual(receipt['status'],'pending_catalog')
