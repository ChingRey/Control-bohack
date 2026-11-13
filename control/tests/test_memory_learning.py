import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents import memory, learning, teaching

class MemoryLearningTests(unittest.TestCase):
 def task(self):
  t={'id':'test','plan':[],'plan_draft':[],'step':0,'files':{'app.js':'const value = input.value;'},'changes':[],'checks':[],
   'messages':[{'channel':'coding','role':'user','content':'我想做待办，刷新之后也保留'},
               {'channel':'teaching','role':'user','content':'输入检查应该先于列表生成，否则会留下空白事项'}]}
  teaching.state(t);return t
 def observation(self):
  return {'capability_id':'verification','level':'independent','explanation':'能提出检查位置，但独立程度需要复核',
    'evidence_ids':[1],'quotes':[{'message_id':1,'quote':'输入检查应该先于列表生成'}]}
 def card(self):
  return {'title':'生成列表前检查输入','kind':'method','when':'处理用户输入时','rule':'在产生列表副作用之前判断输入',
   'verification':'检查正常和空白输入','limits':'当前仅在待办示例讨论，尚未证明通用','tags':['输入'],
   'evidence_ids':[1],'quotes':[{'message_id':1,'quote':'输入检查应该先于列表生成'}]}
 def test_long_history_is_bounded_deduplicated_and_current_prompt_is_exact(self):
  t=self.task();original=t['messages'][0]['content']
  for i in range(250):t['messages'].append({'channel':'coding','role':'assistant' if i%2 else 'user','content':str(i)+'内容'*500})
  t['messages'].append({'channel':'coding','role':'user','content':'当前提示词完整原文'*600})
  t['teaching']['course']['objectives'][0]['evidence_ids']=[0]
  ctx=teaching.context(t,'review');ids=[m['id'] for m in ctx['messages']]
  self.assertEqual(len(ids),len(set(ids)))
  self.assertEqual(next(m['content'] for m in ctx['messages'] if m['id']==len(t['messages'])-1),t['messages'][-1]['content'])
  self.assertEqual(next(m['content'] for m in ctx['messages'] if m['id']==0),original)
  self.assertLess(memory.size(ctx),memory.MAX_CONTEXT_CHARS)
  self.assertGreater(ctx['learning_memory']['omitted_unsummarized_count'],0)
  self.assertEqual(len(t['messages']),253)
 def test_compaction_sources_are_contiguous_and_old_messages_are_unchanged(self):
  t=self.task();t['messages']*=100;before=copy.deepcopy(t['messages']);seen=[]
  def summarize(rows):seen.append(rows);return '学生要求刷新保留；尚未验证掌握。'
  memory.prepare(t,summarize,lambda *a:None)
  s=memory.state(t);self.assertTrue(s['segments']);self.assertEqual(s['segments'][0]['from_id'],0)
  for a,b in zip(s['segments'],s['segments'][1:]):self.assertEqual(a['to_id']+1,b['from_id'])
  self.assertEqual(t['messages'],before)
  end=s['covered_through'];memory.prepare(t,summarize,lambda *a:None)
  self.assertGreaterEqual(s['covered_through'],end)
 def test_compaction_failure_keeps_old_cursor_and_valid_batches(self):
  t=self.task();t['messages']=[{'channel':'coding','role':'user','content':'原始消息'*700} for _ in range(40)]
  with self.assertRaises(ValueError):memory.prepare(t,lambda rows:None,lambda *a:None)
  self.assertEqual(memory.state(t)['covered_through'],-1)
  values=iter(['有效摘要',RuntimeError('transport')])
  def partial(rows):
   value=next(values)
   if isinstance(value,Exception):raise value
   return value
  with patch('agents.memory.SEGMENT_CHARS',8000):
   with self.assertRaises(RuntimeError):memory.prepare(t,partial,lambda *a:None)
  self.assertGreaterEqual(memory.state(t)['covered_through'],0)
 def test_history_tool_cannot_cross_task_or_silently_clip_evidence(self):
  t=self.task();ctx=teaching.context(t,'review')
  result=teaching.dispatch_tool('read_message_history',{'start':0,'limit':2},ctx,t['messages'])
  self.assertEqual(result['messages'][0]['content'],t['messages'][0]['content'])
  with self.assertRaises(ValueError):teaching.dispatch_tool('read_message_history',{'start':-1},ctx,t['messages'])
  with self.assertRaises(ValueError):teaching.dispatch_tool('read_message_history',{'start':0,'limit':1000},ctx,t['messages'])
 def test_fake_student_or_agent_evidence_is_rejected(self):
  t=self.task();ctx=teaching.context(t,'review');item=self.observation()
  item['quotes'][0]['quote']='我已经完全掌握了所有知识'
  with self.assertRaises(ValueError):learning.validate({'observations':[item]},ctx)
  t['messages'][1]['role']='assistant';ctx=teaching.context(t,'review')
  with self.assertRaises(ValueError):learning.validate({'observations':[self.observation()]},ctx)
 def test_transfer_claim_requires_explicit_transfer_submission(self):
  t=self.task();ctx=teaching.context(t,'review');item=self.observation();item['level']='transfer_candidate'
  with self.assertRaises(ValueError):learning.validate({'observations':[item]},ctx)
  ctx['transfer_answer']={'message_id':1}
  self.assertTrue(learning.validate({'observations':[item]},ctx))
 def test_experience_requires_confirmation_and_disable_removes_it(self):
  t=self.task();ctx=teaching.context(t,'review');update={'experiences':[self.card()]}
  learning.apply(t,learning.validate(update,ctx),0,'hash')
  card=learning.state(t)['experiences'][0]
  self.assertEqual(learning.coding_packet(t,'输入检查')['rules'],[])
  with self.assertRaises(ValueError):learning.set_experience(t,card['id'],'confirm',False)
  learning.set_experience(t,card['id'],'confirm',True)
  self.assertEqual(learning.coding_packet(t,'输入检查')['rules'][0]['id'],card['id'])
  learning.set_experience(t,card['id'],'disable',True)
  self.assertEqual(learning.coding_packet(t,'输入检查')['rules'],[])
  self.assertEqual(learning.state(t)['events'][-1]['before']['status'],'confirmed')
  self.assertEqual(learning.coding_packet(self.task(),'输入检查')['rules'],[])
 def test_skill_does_not_unlock_by_message_count_or_model_claim(self):
  t=self.task();learning.apply(t,{'observations':[self.observation()]*3},0,'hash')
  self.assertFalse(any(s['can_install'] for s in learning.readiness(t)))
  with self.assertRaises(ValueError):learning.request_unlock(t,'verification-before-completion',True)
 def test_two_evidence_gates_never_install_unvalidated_skill(self):
  t=self.task()
  for cid in ('verification','change-instruction'):
   for level,ids in [('independent',[0]),('transfer_candidate',[1])]:
    item=self.observation();item.update(capability_id=cid,level=level,evidence_ids=ids)
    learning.apply(t,{'observations':[item]},0,'hash')
  skill=next(x for x in learning.readiness(t) if x['id']=='verification-before-completion')
  self.assertTrue(skill['student_ready_for_review']);self.assertFalse(skill['can_install'])
  learning.request_unlock(t,skill['id'],True)
  self.assertFalse(learning.state(t)['unlock_requests'][0]['applied'])
  with self.assertRaises(ValueError):learning.request_unlock(t,skill['id'],True)
 def test_markdown_export_distinguishes_notes_and_facts(self):
  t=self.task();text=memory.report(t)
  self.assertIn('系统记录',text);self.assertIn('不是掌握证明',text);self.assertIn('尚未整理',text)

 def test_large_source_uses_explicit_excerpts_without_changing_original(self):
  t=self.task();t['files']['app.js']='a'*memory.MAX_CONTEXT_CHARS
  ctx=teaching.context(t,'review')
  self.assertLess(memory.size(ctx),memory.MAX_CONTEXT_CHARS)
  self.assertEqual(ctx['project_files']['total_file_count'],1)
  self.assertEqual(ctx['project_files']['read_tool'],'read_project_file')
  self.assertEqual(len(t['files']['app.js']),memory.MAX_CONTEXT_CHARS)

 def test_large_current_prompt_fails_explicitly_instead_of_truncating(self):
  t=self.task();t['messages'][-1]['content']='a'*memory.MAX_CONTEXT_CHARS
  with self.assertRaisesRegex(ValueError,'超过80000'):teaching.context(t,'review')
  self.assertEqual(len(t['messages'][-1]['content']),memory.MAX_CONTEXT_CHARS)

 def test_invalid_learning_does_not_discard_normal_reply(self):
  from test_teaching import TeachingTests
  fixture=TeachingTests();fixture.setUp()
  output=copy.deepcopy(fixture.good)
  item=self.observation();item['quotes'][0]['quote']='编造不存在的原话'
  output['learning_update']={'observations':[item]}
  result=teaching.validate(output,fixture.ctx)
  self.assertEqual(result['reply'],fixture.good['reply'])
  self.assertEqual(result['learning_update'],{})
  self.assertTrue(result['validation_warnings'])

if __name__=='__main__':unittest.main()
