import sqlite3
import unittest
from agents import knowledge, learning


class KnowledgeTests(unittest.TestCase):
 def candidate(self):
  return {'type':'verified_pattern','title':'空白输入校验','content':'提交前应将输入去除首尾空白，再检查是否为空。',
          'evidence_ids':[1],'quotes':[{'message_id':1,'quote':'输入检查应该先于列表生成'}]}

 def test_teaching_candidate_is_evidence_linked_and_pending(self):
  from test_memory_learning import MemoryLearningTests
  fixture=MemoryLearningTests();task=fixture.task();ctx=__import__('agents.teaching',fromlist=['context']).context(task,'review')
  update={'knowledge_candidates':[self.candidate()]}
  validated=learning.validate(update,ctx)
  learning.apply(task,validated,4,ctx['code_hash'])
  row=learning.state(task)['knowledge_candidates'][0]
  self.assertEqual(row['status'],'pending_review');self.assertFalse(row['verified'])
  self.assertEqual(row['evidence_ids'],[1]);self.assertEqual(row['source_turn'],4)

 def test_unverified_or_invalid_evidence_candidate_is_rejected(self):
  from test_memory_learning import MemoryLearningTests
  from agents import teaching
  task=MemoryLearningTests().task();ctx=teaching.context(task,'review')
  for override in ({'evidence_ids':[0]}, {'quotes':[{'message_id':1,'quote':'not in original'}]}, {'type':'student_state'}, {'title':''}):
   item={**self.candidate(),**override}
   with self.assertRaises(ValueError):learning.validate({'knowledge_candidates':[item]},ctx)
  failure={**self.candidate(),'type':'observed_failure'}
  self.assertTrue(learning.validate({'knowledge_candidates':[failure]},ctx))

 def test_review_gate_project_scope_and_code_version(self):
  from datetime import datetime, timezone
  conn=sqlite3.connect(':memory:');knowledge.initialize(conn)
  task={'id':'task-a','teaching':{'learning':{'knowledge_candidates':[{
   'id':'candidate-a','type':'verified_pattern','title':'空白输入校验','content':'输入空白时应判为空并阻止提交。',
   'evidence_ids':[7],'quotes':[{'message_id':7,'quote':'输入空白时也应视为没有填写'}],
   'source_turn':2,'code_hash':'a'*64,'status':'pending_review','revision':1,
   'created_at':datetime.now(timezone.utc).isoformat()}]}}}
  knowledge.sync_task(conn,task)
  self.assertEqual(knowledge.search(conn,'task-a','空白输入','a'*64),[])
  approved=knowledge.review(task,'candidate-a','approve','local-maintainer','出处与项目约束已复核')
  knowledge.sync_task(conn,task)
  self.assertEqual(approved['status'],'approved')
  found=knowledge.search(conn,'task-a','空白输入','a'*64)
  self.assertEqual(len(found),1);self.assertFalse(found[0]['stale_for_code'])
  self.assertTrue(knowledge.search(conn,'task-a','空白输入','b'*64)[0]['stale_for_code'])
  self.assertEqual(knowledge.search(conn,'task-b','空白输入','a'*64),[])
  knowledge.review(task,'candidate-a','withdraw','local-maintainer','来源已过期')
  knowledge.sync_task(conn,task)
  self.assertEqual(knowledge.search(conn,'task-a','空白输入','a'*64),[])
  conn.close()


if __name__=='__main__':unittest.main()
