import copy
import unittest
from unittest.mock import patch
from agents import teaching_sessions as sessions, evolution_port, knowledge
import test_backend as base

class SessionTests(unittest.TestCase):
 def task(self):
  return {'id':'project','plan':[],'messages':[
   {'channel':'coding','role':'user','content':'Reject whitespace input'},
   {'channel':'coding','role':'assistant','content':'Created input validation'},
   {'channel':'teaching','role':'user','content':'I checked whitespace and normal input'},
   {'channel':'teaching','role':'assistant','content':'Remember to check both cases'}]}
 def test_finish_covers_both_dialogues_and_is_idempotent(self):
  t=self.task();opened=sessions.open_session(t,{'request_id':'open'})
  body={'request_id':'finish','teaching_session_id':opened['teaching_session_id'],'confirmed':True}
  r=sessions.finish(t,body,{})
  self.assertEqual(r['source_message_ids'],[0,1,2,3]);self.assertEqual(r['knowledge_status'],'mock_only')
  self.assertEqual(sessions.finish(t,body,{}),r)
  rows=t['teaching']['learning']['knowledge_candidates'];self.assertEqual(len(rows),1)
  with self.assertRaises(ValueError):knowledge.review(t,rows[0]['id'],'approve','reviewer')
 def test_invalid_extraction_does_not_complete_session_or_write_candidates(self):
  t=self.task();opened=sessions.open_session(t,{'request_id':'open'})
  bad={'mode':'model','items':[{'type':'project_fact','title':'x','content':'x','when':'x','limits':'x','evidence_ids':[99],'quotes':[]}]}
  with patch.object(sessions.DISTILLER,'extract',return_value=bad):
   with self.assertRaises(ValueError):sessions.finish(t,{'request_id':'finish','teaching_session_id':opened['teaching_session_id'],'confirmed':True},{})
  self.assertEqual(t['teaching_sessions'][0]['status'],'active');self.assertNotIn('teaching',t)
 def test_evolution_is_only_an_idempotent_placeholder(self):
  t=self.task();before=copy.deepcopy(t['messages']);body={'request_id':'evolve','strategy_version':'v1'}
  result=evolution_port.evolve(t,body)
  self.assertEqual(result['mode'],'mock');self.assertIsNone(result['strategy']);self.assertFalse(result['applied'])
  self.assertEqual(result,evolution_port.evolve(t,body));self.assertEqual(before,t['messages'])
  with self.assertRaises(ValueError):evolution_port.evolve(t,{**body,'strategy_version':'v2'})

class PostTeachingApiTests(unittest.TestCase):
 setUpClass=classmethod(base.BackendTest.setUpClass.__func__)
 tearDownClass=classmethod(base.BackendTest.tearDownClass.__func__)
 call=base.BackendTest.call
 def test_mock_finish_is_persisted_but_never_retrieved_by_coding(self):
  t=self.call('/tasks',{'coding_mode':'opencode'});p='/tasks/'+t['id']
  task=base.b.load(t['id']);task['messages'].append({'channel':'teaching','role':'user','content':'I checked the project result'});base.b.save(task)
  opened=self.call(p+'/teaching/sessions/open',{'request_id':'open'})
  r=self.call(p+'/teaching/sessions/finish',{'request_id':'finish','teaching_session_id':opened['teaching_session_id'],'confirmed':True})
  self.assertEqual(r['knowledge_status'],'mock_only')
  self.assertEqual(self.call(p+'/knowledge/search',{'query':'Mock placeholder'})['items'],[])
  saved=base.b.load(t['id']);self.assertEqual(saved['teaching_sessions'][0]['status'],'completed')
  with base.b.connection() as c:self.assertEqual(knowledge.list_task(c,t['id'])[0]['status'],'mock_only')
  self.assertEqual(self.call(p+'/teaching/evolve',{'request_id':'evolve'})['mode'],'mock')
 def test_future_distiller_feeds_existing_review_and_retrieval(self):
  t=self.call('/tasks',{'coding_mode':'opencode'});p='/tasks/'+t['id']
  task=base.b.load(t['id']);task['messages'].append({'channel':'teaching','role':'user','content':'Reject whitespace input and verify normal input'});base.b.save(task)
  opened=self.call(p+'/teaching/sessions/open',{'request_id':'open'})
  fixture={'mode':'model','items':[{'type':'project_fact','title':'whitespace input','content':'Reject whitespace input; verify normal input.','when':'whitespace input','limits':'current project','evidence_ids':[len(task['messages'])-1],'quotes':[{'message_id':len(task['messages'])-1,'quote':'Reject whitespace input'}]}]}
  with patch.object(sessions.DISTILLER,'extract',return_value=fixture):
   result=self.call(p+'/teaching/sessions/finish',{'request_id':'finish','teaching_session_id':opened['teaching_session_id'],'confirmed':True})
  self.assertEqual(self.call(p+'/knowledge/search',{'query':'whitespace input'})['items'],[])
  self.call(p+'/knowledge/'+result['candidate_ids'][0]+'/review',{'confirmed':True,'decision':'approve','reviewer':'test'})
  found=self.call(p+'/knowledge/search',{'query':'whitespace input'})['items']
  self.assertEqual(found[0]['id'],result['candidate_ids'][0]);self.assertIn('current project',found[0]['content'])
