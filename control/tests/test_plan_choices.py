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
   self.assertEqual(code,202);self.assertTrue(run.call_args.kwargs.get('planning'));self.assertEqual(t['plan'],[])

 def test_queued_draft_feedback_revises_instead_of_repeating_choice_prompt(self):
  calls=[]
  def execute(files,payload,*args):
   calls.append(payload)
   return {'text':'开发计划：\n1. 创建计分页面\n2. 实现30秒计时','files':files,'events':[]}
  with patch.object(b.opencode_executor,'execute',side_effect=execute):
   code,_=self.h.call(self.h.path+'/chat/send',{'channel':'coding','message':'去掉音效，第一版只要计分和30秒倒计时','request_id':'plain-revision'})
   self.assertEqual(code,202);t=self.h.wait()
  self.assertEqual(t['plan'],[]);self.assertEqual(t['plan_draft'],['创建计分页面','实现30秒计时'])
  self.assertEqual(calls[0]['interaction_mode'],'planning')
  self.assertNotIn('选择 ✓',t['messages'][-1]['content'])

 def test_generic_checkmark_acknowledges_reply_without_approving_phase(self):
  t=b.load(self.h.task['id']);t['plan_draft']=[];b.save(t)
  index=max(i for i,m in enumerate(t['messages']) if m.get('channel')=='coding' and m.get('role')=='assistant')
  body={'message_id':index,'expected_content':t['messages'][index]['content'],'request_id':'reply-check'}
  self.assertEqual(self.h.call(self.h.path+'/coding/reply-accept',body)[0],200)
  self.assertEqual(self.h.call(self.h.path+'/coding/reply-accept',body)[0],200)
  t=b.load(t['id']);self.assertEqual(len(t['coding_reply_acceptances']),1);self.assertEqual(t['plan'],[])

 def test_generic_checkmark_cannot_bypass_plan_approval(self):
  t=b.load(self.h.task['id']);index=max(i for i,m in enumerate(t['messages']) if m.get('channel')=='coding' and m.get('role')=='assistant')
  self.assertEqual(self.h.call(self.h.path+'/coding/reply-accept',{'message_id':index,'expected_content':t['messages'][index]['content'],'request_id':'wrong-kind'})[0],400)
