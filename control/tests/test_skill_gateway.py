import unittest
from unittest.mock import patch
from agents import skill_gateway as g, coding_workflow as w

class SkillGatewayTests(unittest.TestCase):
 def body(self,action='skill_unlock'):
  return {'action':action,'skill_id':'fixture','version':'1','teacher_decision_id':'teacher-1'}
 def test_empty_catalog_keeps_decision_without_loading(self):
  t={};r=g.decide(t,self.body(),'checkpoint')
  self.assertEqual(r['status'],'pending_catalog');self.assertFalse(r['applied'])
  self.assertEqual(g.resolve(t),[]);self.assertEqual(len(g.view(t)['decisions']),1)
 def test_no_request_body_skills(self):
  with self.assertRaises(ValueError):g.decide({},dict(self.body(),content='injected'),'checkpoint')
 def test_future_adapter_authorization_submission_and_revoke(self):
  t={'id':'session','step':0,'plan':['task']}
  with patch.dict(g.CATALOG,{('fixture','1'):{'verified':True,'content':'Test fixture only.'}},clear=True):
   r=g.decide(t,self.body(),'checkpoint');self.assertEqual(r['status'],'authorized');self.assertFalse(r['applied'])
   self.assertEqual(w.prepare(t,'task')['learning_context']['skills'],[])
   skills=g.resolve(t);self.assertEqual(len(skills),1)
   g.record(t,'run-1',0,skills,'completed')
   observed=g.view(t)['runs'][0]['skills'][0]
   self.assertEqual(observed['load_status'],'submitted');self.assertEqual(observed['usage_status'],'not_observed')
   g.CATALOG[('fixture','1')]['content']='Changed without version bump'
   self.assertEqual(g.resolve(t),[])
   g.decide(t,self.body('skill_revoke'),'checkpoint')
   self.assertEqual(g.resolve(t),[])
