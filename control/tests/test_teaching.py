import copy
import json
import os
import unittest
import time
from urllib.error import HTTPError
from unittest.mock import patch
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.teaching import context, validate, TeachingAgent, run

class TeachingTests(unittest.TestCase):
 def setUp(self):
  self.t={'plan':[],'step':0,'files':{'app.js':'const title = input.value;'},'changes':[],'checks':[],
   'messages':[{'channel':'coding','role':'user','content':'我想做待办网站'},
               {'channel':'teaching','role':'user','content':'应该先检查输入，空格没有内容'}]}
  self.ctx=context(self.t,'message')
  self.good={'reply':'为什么空格会被接受？','next_phase':'explain','hint_level':1,
   'assessment':'developing','student_evidence_ids':[1],
   'citations':[{'file':'app.js','line':1,'quote':'const title = input.value;'}],
   'source_ids':['mdn-trim'],'issue_kind':'hypothesis','upgrade_suggestion':'',
   'teaching_action':'ask','transfer_question':'',
   'plan':{'goal':'判断输入','reason':'学生已提出空白情况','next_step':'解释依据','open_questions':[]}}
 def test_context_contains_real_source_and_student_prompt(self):
  self.assertEqual(self.ctx['files']['app.js'][0]['line'],1)
  self.assertEqual(self.ctx['messages'][0]['content'],'我想做待办网站')
  self.assertEqual(self.ctx['check_type'],'source_markers_only_not_behavioral')
 def test_validation_rejects_skips_fake_citations_and_unearned_mastery(self):
  self.assertEqual(validate(self.good,self.ctx),self.good)
  for key,value in [('next_phase','unknown'),('citations',[{'file':'app.js','line':9,'quote':'fake'}]),('assessment','candidate')]:
   output=copy.deepcopy(self.good);output[key]=value
   with self.assertRaises(ValueError): validate(output,self.ctx)
 def test_bad_student_reference_does_not_discard_teaching_reply(self):
  output=copy.deepcopy(self.good);output['student_evidence_ids']=[100]
  result=validate(output,self.ctx)
  self.assertEqual(result['reply'],self.good['reply']);self.assertEqual(result['assessment'],'insufficient')
  self.assertTrue(result['validation_warnings'])
  output=copy.deepcopy(self.good);output['student_evidence_ids']=['1']
  self.assertEqual(validate(output,self.ctx)['student_evidence_ids'],[1])
 def test_sample_never_claims_mastery(self):
  with patch.dict(os.environ,{'TEACHING_MODE':'sample'}): reply=run(self.t)
  self.assertIn('示例',reply);self.assertEqual(self.t['teaching']['assessment'],'insufficient')
 def test_model_transport_and_audit(self):
  class Response:
   def __init__(self,data):self.data=data
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps(self.data).encode()
  self_good=self.good
  tool={'id':'call-1','type':'function','function':{'name':'read_teaching_skill','arguments':'{"name":"diagnose"}'}}
  responses=[Response({'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[tool]}}]}),Response({'choices':[{'message':{'content':json.dumps(self_good)}}]})]
  with patch.dict(os.environ,{'TEACHING_MODE':'model','TEACHING_MODEL':'test-model','TEACHING_ENDPOINT':'http://localhost:1234/v1/chat/completions','TEACHING_API_KEY':'test-secret'}),patch('agents.teaching.urlopen',side_effect=responses) as send:
   run(self.t)
   payload=json.loads(send.call_args_list[0].args[0].data)
   self.assertIn('files',json.loads(payload['messages'][1]['content']))
  self.assertEqual(self.t['teaching']['phase'],'explain')
  self.assertNotIn('test-secret',json.dumps(self.t))
  self.assertEqual(self.t['teaching']['turns'][0]['provider']['model'],'test-model')
  self.assertEqual(self.t['teaching']['turns'][0]['tools'][0]['name'],'read_teaching_skill')

 def test_autonomous_actions_can_change_focus_without_fixed_order(self):
  output=copy.deepcopy(self.good);output['next_phase']='transfer'
  output['teaching_action']='ask_transfer';output['transfer_question']='如何处理全是空格的昵称？'
  self.assertEqual(validate(output,self.ctx)['next_phase'],'transfer')

 def test_tools_cannot_read_outside_project_or_write(self):
  from agents.teaching import dispatch_tool
  for name,args in [('read_project_file',{'path':'../../secret'}),('read_teaching_skill',{'name':'../../secret'}),('write_file',{'path':'app.js'})]:
   with self.assertRaises(ValueError):dispatch_tool(name,args,self.ctx)

 def test_course_memory_survives_new_code_and_long_conversation(self):
  self.good['course_update']={'summary':'学生提出空白输入问题，原因尚待解释。','resume_note':'接着解释输入处理，不重新开课。','addressed_objective_ids':['input-validation']}
  with patch('agents.teaching.TeachingAgent.respond',return_value=self.good):run(self.t)
  self.t['files']['app.js']='const title = input.value.trim();'
  for i in range(90):self.t['messages'].append({'role':'user','channel':'teaching','content':f'后续消息{i}'})
  ctx=context(self.t,'review')
  self.assertTrue(ctx['project_change']['code_changed'])
  self.assertIn('原因尚待解释',ctx['course']['summary'])
  self.assertIn(1,[m['id'] for m in ctx['student_evidence']])
  self.assertEqual(ctx['course']['objectives'][1]['evidence_ids'],[1])
  self.assertEqual(len(ctx['course']['checkpoints']),1)

 def test_mindmap_is_structured_and_bounded(self):
  output=copy.deepcopy(self.good)
  output['mindmap']={'title':'待办项目','branches':[{'label':'计划草稿','children':[{'label':'明确目标'}]}]}
  self.assertEqual(validate(output,self.ctx)['mindmap']['title'],'待办项目')
  output['mindmap']['branches']*=5
  with self.assertRaises(ValueError):validate(output,self.ctx)

 def test_citation_rejects_substring_and_accepts_short_complete_line(self):
  for quote in (';', 'a', 'input.value'):
   output=copy.deepcopy(self.good);output['citations'][0]['quote']=quote
   with self.assertRaises(ValueError):validate(output,self.ctx)
  ctx=copy.deepcopy(self.ctx);ctx['files']['app.js'][0]['text']='  x();'
  output=copy.deepcopy(self.good);output['citations'][0]['quote']='x();'
  self.assertEqual(validate(output,ctx)['citations'][0]['quote'],'x();')

 def test_preloaded_skills_do_not_require_redundant_tool_call(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return json.dumps({'choices':[{'message':{'content':json.dumps(output)}}]}).encode()
  output=self.good
  with patch.dict(os.environ,{'TEACHING_MODE':'model','TEACHING_MODEL':'test','TEACHING_ENDPOINT':'http://localhost:1234/chat'}),patch('agents.teaching.urlopen',return_value=Response()) as send:
   run(self.t)
  self.assertEqual(send.call_count,1)
  self.assertIn('diagnose',self.t['teaching']['turns'][-1]['loaded_skills'])

 def test_transient_errors_retry_but_auth_errors_do_not(self):
  from agents.teaching import request_model
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return b'{"ok":true}'
  error=lambda status:HTTPError('http://localhost',status,'test',{'Retry-After':'0'},None)
  budget={'attempts':0,'deadline':time.monotonic()+120}
  with patch('agents.teaching.urlopen',side_effect=[error(429),error(503),Response()]) as send,patch('agents.teaching.time.sleep') as sleep:
   self.assertTrue(request_model(None,budget,lambda *a:None)['ok'])
  self.assertEqual(budget['attempts'],3);self.assertEqual(sleep.call_count,2)
  for status in (401,403):
   with patch('agents.teaching.urlopen',side_effect=error(status)) as send,patch('agents.teaching.time.sleep') as sleep:
    with self.assertRaises(HTTPError):request_model(None,{'attempts':0,'deadline':time.monotonic()+120},lambda *a:None)
    self.assertEqual(send.call_count,1);sleep.assert_not_called()

 def test_retry_budget_and_total_deadline_are_bounded(self):
  from agents.teaching import request_model
  error=HTTPError('http://localhost',429,'test',{},None)
  budget={'attempts':4,'deadline':time.monotonic()+120}
  with patch('agents.teaching.urlopen',side_effect=error) as send,patch('agents.teaching.time.sleep') as sleep:
   with self.assertRaises(HTTPError):request_model(None,budget,lambda *a:None)
   self.assertEqual(send.call_count,1);sleep.assert_not_called()
  with patch('agents.teaching.urlopen') as send:
   with self.assertRaises(ValueError):request_model(None,{'attempts':0,'deadline':time.monotonic()-1},lambda *a:None)
   send.assert_not_called()

if __name__=='__main__':unittest.main()
