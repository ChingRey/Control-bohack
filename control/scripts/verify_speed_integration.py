"""Isolated HTTP/browser check for upstream progress and explicit Coding execution.

The Coding result and provider SSE are fixtures; no account calls or student writes.
"""
import io
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import backend as b
from agents import browser_runner as br,teaching,teaching_evolution as e
import test_teaching_evolution as fixture

out=ROOT/'data/verification';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as folder,patch.object(b,'DATA',Path(folder)),patch.object(b,'DB',Path(folder)/'records.sqlite3'),patch.dict(os.environ,{'TEACHING_MODE':'model','TEACHING_PROVIDER':'siliconflow','TEACHING_MODEL':'zai-org/GLM-5.3-Flash','SILICONFLOW_API_KEY':'fixture-only-key'}):
 t=fixture.task();t.update(id=str(uuid.uuid4()),title='加速流程验证',plan=['实现计分'],plan_draft=[],changes=[],checks=[],files={},checkpoint_delivery='automatic')
 t['messages']=[{'channel':'coding','role':'user','content':'先讨论计分的实现'}, {'channel':'coding','role':'assistant','content':'可以先实现点击按钮加一。'}]
 t.pop('teaching_evolution',None);teaching.state(t);b.coding_workflow.confirm(t);b.save(t)
 calls=[]
 def execute(files,payload,*args):
  callback=b.opencode_executor._PROGRESS.get()
  callback({'stage':'tool','detail':'正在读取相关文件','model_rounds':1,'completed_tools':1,'elapsed_seconds':.2})
  time.sleep(1)
  callback({'stage':'verifying','detail':'正在核对本轮实际文件','model_rounds':2,'completed_tools':2,'elapsed_seconds':1.2})
  return {'text':'已实现点击计分，请检查。','files':{'game.js':'let score = 0;\nfunction addPoint() { score += 1; }'},'events':[]}
 def provider(req,**kwargs):
  calls.append(json.loads(req.data))
  chunks=[]
  for delta,finish in [({'reasoning_content':'fixture private reasoning'},None),({'content':'分数是保存当前结果的变量。'},None),({'content':'点击一次，分数从零变成一。'},None),({},'stop')]:
   chunks.append('data: '+json.dumps({'choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n')
  chunks.append('data: [DONE]\n\n')
  class Stream(io.BytesIO):
   headers={'Content-Type':'text/event-stream'}
   def readline(self,*args):
    time.sleep(.09)
    return super().readline(*args)
  return Stream(''.join(chunks).encode())
 class Handler(b.Handler):
  def log_message(self,*args):pass
 probe=out/'speed-browser';(probe/'scripts').mkdir(parents=True,exist_ok=True)
 source=(ROOT/'scripts/browser_cases.cjs').read_text(encoding='utf8')
 checks='''
 const assert=async(name,expression)=>{const ok=await evaluate(expression);results.push({name,passed:!!ok});if(!ok)throw Error(name)};
 const wait=ms=>new Promise(r=>setTimeout(r,ms));
 await evaluate(`enterProject(PROJECT_ID)`);await wait(400);
 await assert('Coding separates reply acknowledgement and stage execution',`document.querySelector('#coding-messages').textContent.includes('确认这条回复')&&document.querySelector('#coding-messages').textContent.includes('执行当前阶段')`);
 await evaluate(`Array.from(document.querySelectorAll('#coding-messages button')).find(b=>b.textContent==='✓ 确认这条回复').click()`);await wait(400);
 await assert('acknowledging a reply does not execute or advance a phase',`task.coding_reply_acceptances.length===1&&task.step===0&&!task.coding_run&&!Object.keys(task.files||{}).length`);
 await evaluate(`Array.from(document.querySelectorAll('#coding-messages button')).find(b=>b.textContent==='执行当前阶段').click()`);await wait(350);
 await evaluate(`api('/tasks/'+task.id).then(t=>{task=t;render()})`);await wait(100);
 await assert('in-flight Coding progress reaches page with tool and model counts',`task.coding_run.status==='running'&&task.coding_run.completed_tools===1&&document.querySelector('#coding-messages').textContent.includes('次工具操作完成')`);
 await wait(2200);
 await evaluate(`api('/tasks/'+task.id).then(t=>{task=t;render()})`);await wait(200);
 await assert('real completion records progress and hands off to Teacher',`task.coding_run.status==='completed'&&task.coding_run.progress_trace.length>=2&&task.teaching_run.status==='completed'`);
 await assert('Teacher retains one streamed call and measured timings',`task.teaching.turns.at(-1).request_attempts===1&&task.teaching.turns.at(-1).request_timings[0].first_content_seconds>=0`);
 await assert('no hidden reasoning appears in teaching chat',`!document.querySelector('#teaching-messages').textContent.includes('fixture private reasoning')&&document.querySelector('#teaching-messages').textContent.includes('分数是保存当前结果的变量')`);
 await assert('experience and prepared source versions remain traceable',`task.teaching_run.experience_context.revision>=1&&task.teaching_run.context_materials.source_lines>0&&task.teaching.turns.at(-1).experience_context.validation_focus!==undefined`);
 await assert('experience matrix entry and layout survive integration',`document.querySelector('#evolution-open').textContent==='经验库'&&!!document.querySelector('#coding-reset')`);
 '''.replace('PROJECT_ID',json.dumps(t['id']))
 source=source.replace('  if(packet.screenshot){',checks+'\n  if(packet.screenshot){',1)
 (probe/'scripts/browser_cases.cjs').write_text(source,encoding='utf8')
 with patch.object(b.opencode_executor,'CONFIG',{'key':'fixture-only-key','model':'fixture','url':'https://example.invalid'}),patch.object(b.opencode_executor,'binary',return_value='fixture-cli'),patch.object(b.opencode_executor,'execute',side_effect=execute),patch.object(teaching,'urlopen',side_effect=provider),patch.object(b,'start_organizer'),patch.object(e,'pending',return_value=False),patch.object(br,'ROOT',probe):
  result=br.run({}, {},[{'action':'wait','ms':500},{'action':'assert_exists','selector':'#evolution-open'}],handler=Handler,screenshot=out/'speed-integration.png')
 result.update(provider_calls=len(calls),fixture_model=True)
 result['single_pass_payload']=bool(calls and calls[0].get('stream') and 'tools' not in calls[0] and calls[0].get('thinking_budget')==1024)
 (out/'speed-integration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(result,ensure_ascii=False))
 if not result['passed'] or not result['single_pass_payload']:raise SystemExit(1)
