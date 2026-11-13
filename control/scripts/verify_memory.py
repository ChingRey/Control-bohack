"""Offline plumbing benchmark; summarizer is a fixture, never a model-quality claim."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents import teaching, memory

def main():
 task={'id':'offline-fixture','plan':['添加与完成','刷新保留'],'plan_draft':[],'step':1,'changes':[],'checks':[],
       'files':{'app.js':'const input = document.querySelector("input");'},'messages':[]}
 for i in range(200):
  task['messages'].append({'channel':'coding','role':'user' if i%2==0 else 'assistant',
    'content':f'第{i}条演示记录：'+('讨论开发计划、实现状态与验证办法。'*30)})
 task['messages'][0]['content']='早期约束：不能联网，刷新后保留数据。'
 task['messages'].append({'channel':'coding','role':'user','content':'当前提示词：先检查输入边界，再说明验证办法。'})
 teaching.state(task)
 original=json.dumps(task['messages'],ensure_ascii=False)
 baseline={'messages':task['messages'][-50:],'student_evidence':[x for x in task['messages'] if x['role']=='user'][-80:]}
 calls=[]
 def fixture_summary(rows):
  calls.append([rows[0]['id'],rows[-1]['id']])
  return '演示摘要：'+('早期约束不能联网，刷新后保留。' if rows[0]['id']==0 else '')+'本段讨论开发与验证；不证明学生掌握。'
 for _ in range(20):
  before=memory.state(task)['covered_through'];memory.prepare(task,fixture_summary,lambda *a:None)
  if memory.state(task)['covered_through']==before:break
 ctx=teaching.context(task,'review')
 assert original==json.dumps(task['messages'],ensure_ascii=False)
 assert ctx['current_focus']['coding_prompt_id']==200
 assert next(x for x in ctx['messages'] if x['id']==200)['content']==task['messages'][-1]['content']
 assert memory.size(ctx)<memory.MAX_CONTEXT_CHARS
 result={'mode':'offline_fixture_not_real_model','messages':201,'old_history_characters':memory.size(baseline),
  'new_full_context_characters':memory.size(ctx),'summary_batches':calls,'current_prompt_preserved':True,
  'raw_history_preserved':True,'covered_through':memory.state(task)['covered_through'],
  'limitation':'摘要文本由固定测试函数生成，只验证数据范围和上下文组织，不评估真实摘要质量或教学效果。'}
 target=Path(__file__).resolve().parents[1]/'docs/experiments/memory-offline.json';target.parent.mkdir(exist_ok=True)
 target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
