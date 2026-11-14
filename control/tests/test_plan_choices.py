import unittest
from unittest.mock import patch
import test_checkpoints as fixture
import backend as b

class PlanChoiceTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
  t=b.load(self.h.task['id']);t.update(plan=[],plan_draft=['创建页面','实现交互'],checkpoint_delivery='manual');b.save(t)
 def test_reject_is_saved_without_executing(self):
  with patch.object(b,'start_coding') as run:
   code,t=self.h.call(self.h.path+'/coding/plan-decision',{'choice':'revise','request_id':'reject','expected_plan':['创建页面','实现交互']})
  self.assertEqual(code,200);run.assert_not_called();self.assertEqual(t['plan'],[])
  self.assertEqual(t['plan_decision']['choice'],'revise')
 def test_approve_starts_once_and_rejects_stale_choice(self):
  with patch.object(b.opencode_executor,'execute',side_effect=self.h.execute) as execute:
   wrong={'choice':'approve','request_id':'wrong','expected_plan':['旧草稿']}
   self.assertEqual(self.h.call(self.h.path+'/coding/plan-decision',wrong)[0],400)
   body={'choice':'approve','request_id':'accept','expected_plan':['创建页面','实现交互']}
   self.assertEqual(self.h.call(self.h.path+'/coding/plan-decision',body)[0],202)
   t=self.h.wait()
   self.assertEqual(t['plan'],body['expected_plan']);self.assertEqual(t['step'],0)
   self.assertEqual(self.h.call(self.h.path+'/coding/plan-decision',body)[0],200)
   self.assertEqual(execute.call_count,1)
 def test_free_text_cannot_approve_a_plan(self):
  for message in ('我确认了','直接写文件','按这个计划开始做吧'):
   with patch.object(b,'start_coding') as run:
    code,t=self.h.call(self.h.path+'/coding/messages',{'message':message})
   self.assertEqual(code,200);run.assert_not_called();self.assertEqual(t['plan'],[])
