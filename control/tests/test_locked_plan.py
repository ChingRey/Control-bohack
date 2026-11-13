import unittest
from agents import coding_workflow as w
class LockedPlanTests(unittest.TestCase):
 def test_locked_plan_ignores_model_changes(self):
  t={'plan':['A','B'],'plan_draft':['A','B']};self.assertFalse(w.sync_plan(t,'开发计划：\n1. X'));self.assertEqual(t['plan_draft'],['A','B'])
 def test_only_student_acceptance_advances(self):
  t={'plan':['A','B'],'step':0};w.confirm(t)
  with self.assertRaises(ValueError):w.accept_phase(t)
  w.state(t)['checkpoints'][0]['status']='executed_pending_review'
  self.assertEqual(t['step'],0);w.accept_phase(t);self.assertEqual(t['step'],1)
  with self.assertRaises(ValueError):w.accept_phase(t)
