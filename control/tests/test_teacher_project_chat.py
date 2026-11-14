import copy
import os
import unittest
from unittest.mock import patch
from agents import teaching

class TeacherProjectChatTests(unittest.TestCase):
 def task(self):
  return {'id':'session','mode':'opencode','title':'Dinosaur','plan':['Jump'],'plan_draft':['Jump'],'step':0,
   'files':{'src/dinosaur.js':'export const height = 42;'},'changes':[],'checks':[],
   'messages':[{'channel':'coding','role':'user','content':'Build a dinosaur game'},
    {'channel':'coding','role':'assistant','content':'Created src/dinosaur.js'},
    {'channel':'teaching','role':'user','content':'Explain the height'}]}
 def test_shared_context_has_dialogue_and_nested_source_without_lesson(self):
  ctx=teaching.context(self.task(),'message')
  self.assertEqual(ctx['interaction_mode'],'project_chat')
  self.assertTrue(any(m['channel']=='coding' and m['role']=='assistant' for m in ctx['messages']))
  self.assertIn('src/dinosaur.js',[f['path'] for f in ctx['project_files']['files']])
  self.assertEqual(ctx['loaded_skills'],{})
  self.assertNotIn('lesson',ctx);self.assertNotIn('knowledge_map',ctx)
 def test_plain_response_does_not_require_grading_json_or_write_files(self):
  t=self.task();before=copy.deepcopy(t['files']);seen=[]
  def request(config,messages,*args,**kwargs):
   seen.append((messages,kwargs));return object()
  with patch.dict(os.environ,{'TEACHING_MODE':'model','TEACHING_API_KEY':'fixture-key','TEACHING_MODEL':'fixture-model'}),patch.object(teaching.memory,'prepare'),patch.object(teaching.providers,'request',side_effect=request),patch.object(teaching,'request_model',return_value={'choices':[{'message':{'content':'The height is 42 in src/dinosaur.js:1.'}}]}):
   reply=teaching.run(t)
  self.assertIn('42',reply);self.assertEqual(before,t['files'])
  self.assertFalse(seen[0][1]['json_mode'])
  names={x['function']['name'] for x in seen[0][1]['tools']}
  self.assertEqual(names,{'read_project_file','read_message_history'})
  self.assertEqual(t['teaching']['turns'][-1]['result']['mode'],'project_chat')
 def test_teacher_write_call_is_rejected_and_read_uses_snapshot(self):
  t=self.task();ctx=teaching.context(t,'message');before=copy.deepcopy(t['files'])
  class Agent:
   mode='model'
   config={}
   history=t['messages']
   project_source=t['files']
   request_budget={'attempts':0,'deadline':0}
  agent=Agent();seen=[]
  responses=[{'choices':[{'message':{'role':'assistant','tool_calls':[
   {'id':'read','function':{'name':'read_project_file','arguments':'{"path":"src/dinosaur.js","start_line":1,"limit":1}'}},
   {'id':'write','function':{'name':'write','arguments':'{"path":"src/dinosaur.js","content":"changed"}'}}
  ]}}]}, {'choices':[{'message':{'content':'Read-only review finished.'}}]}]
  def request(config,messages,*args,**kwargs):seen.append(copy.deepcopy(messages));return None
  with patch.object(teaching.providers,'request',side_effect=request),patch.object(teaching.providers,'normalize',side_effect=lambda config,x:x),patch.object(teaching,'request_model',side_effect=responses):
   teaching.project_chat(agent,ctx,lambda *args:None)
  self.assertEqual(t['files'],before)
  tool_messages=[m for m in seen[-1] if m['role']=='tool']
  self.assertIn('export const height = 42;',tool_messages[0]['content'])
  self.assertIn('error',tool_messages[1]['content'])
  self.assertEqual([x['success'] for x in agent.tool_trace],[True,False])
