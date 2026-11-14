"""Checkmark-only chat flow in a real browser; isolated DB and simulated Coding transport."""
import json,os,sys,tempfile,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import browser_runner


def main():
 out=b.ROOT/'data/verification';out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as temp,patch.object(b,'DATA',Path(temp)),patch.object(b,'DB',Path(temp)/'records.sqlite3'),patch.dict(os.environ,{'TEACHING_MODE':'sample'}):
  tid=str(uuid.uuid4());t={'id':tid,'title':'对勾与直接修改验收','mode':'opencode','stage':'created','step':0,'plan':[],
    'plan_draft':['创建页面','添加音效'],'plan_decision':{'choice':'revise','request_id':'old-reject'},'changes':[],'checks':[],
    'checkpoint_delivery':'manual','messages':[{'role':'assistant','channel':'coding','content':'开发计划：1. 创建页面；2. 添加音效'}]}
  b.teaching.state(t);b.coding_workflow.state(t);b.save(t);calls=[]
  def execute(files,packet,*args):
   calls.append(packet)
   if packet.get('interaction_mode')=='planning':
    return {'text':'开发计划：\n1. 创建计分页面\n2. 实现计时功能','files':files,'events':[]}
   return {'text':'当前阶段已修改，等待你的确认。','files':{**files,'game.js':'export const revision='+str(len(calls))+';'},'events':[]}
  class Handler(b.Handler):
   def log_message(self,*args):pass
   def reply(self, code, value, *args):
    # Persistent background status must not lock foreground checkmarks, including on reload.
    if isinstance(value,dict) and value.get('id')==tid:
     value={**value,'organizer_run':{'status':'running','detail':'background fixture'},'experience_run':{'status':'running'}}
    return super().reply(code,value,*args)
   def do_GET(self):
    if self.path in ('/','/index.html'):
     html=(b.ROOT/'frontend/index.html').read_text(encoding='utf8').replace('<head>','<head><script>localStorage.setItem("control-workbench-task",'+json.dumps(tid)+')</script>',1)
     return self.reply(200,html.encode(),'text/html; charset=utf-8')
    return super().do_GET()
  cases=[]
  def step(action,selector=None,**kw):cases.append({'action':action,**({'selector':selector} if selector else {}),**kw})
  step('wait',ms=700);step('assert_count','#coding-messages .plan-choice',count=1)
  step('assert_count','#coding-messages .plan-choice.revise',count=0)
  step('fill','#coding-input',value='去掉音效，只要计分和计时');step('click','#coding-form button.primary');step('wait',ms=1200)
  step('assert_text','#coding-messages',text='实现计时功能');step('assert_count','#coding-messages .plan-choice',count=1)
  step('click','#coding-messages .plan-choice.approve');step('wait',ms=1400)
  step('assert_text','#coding-messages',text='本阶段通过，继续下一阶段')
  step('fill','#coding-input',value='红色，大一点');step('click','#coding-form button.primary');step('wait',ms=1400)
  step('assert_count','#coding-messages .plan-choice',count=1);step('assert_text','#coding-messages',text='本阶段通过，继续下一阶段')
  step('click','#coding-messages .plan-choice.approve');step('wait',ms=1400)
  step('assert_text','#coding-messages',text='本阶段通过，完成开发');step('click','#coding-messages .plan-choice.approve');step('wait',ms=500)
  step('assert_text','#coding-messages',text='已完成');step('assert_count','#coding-messages .plan-choice.revise',count=0)
  with patch.object(b.opencode_executor,'execute',side_effect=execute),patch.object(b.opencode_executor,'binary',return_value='fixture'),patch.object(b.opencode_executor,'CONFIG',{'key':'fixture','model':'fixture','url':'https://example.invalid'}):
   result=browser_runner.run({}, {},cases,handler=Handler,screenshot=out/'coding-checkmarks-ui.png')
  final=b.load(tid)
  checks={'plain_text_revises_draft':bool(calls) and calls[0]['interaction_mode']=='planning',
    'same_stage_rework':len(calls)>=3 and calls[1]['phase_index']==calls[2]['phase_index']==0,
    'all_phases_accepted':final['step']==2,'one_extra_stage_only':len(calls)==4,
    'background_does_not_block_checkmark':result['passed'],'no_reject_choice_required':not final.get('plan_decision',{}).get('choice')=='revise'}
  result.update(checks=checks,real_model=False,kind='checkmark_only_real_browser_acceptance');result['passed']=result['passed'] and all(checks.values())
  (out/'coding-checkmarks-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps({'passed':result['passed'],'checks':checks,'last_steps':result['results'][-2:]},ensure_ascii=False))
  if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
