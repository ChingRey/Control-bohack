"""Isolated real-browser acceptance; deterministic provider fixtures, no account calls."""
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import teaching_evolution as e, browser_runner


def main():
 out=b.ROOT/'data/verification';out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as temp,patch.object(b,'DATA',Path(temp)),patch.object(b,'DB',Path(temp)/'records.sqlite3'),patch.dict(os.environ,{'TEACHING_MODE':'model'}):
  tid=str(uuid.uuid4())
  messages=[{'role':'user','channel':'teaching','content':'状态是什么意思？'},
            {'role':'assistant','channel':'teaching','content':'先看例子：分数变量从3变成4，再把4显示到界面。'},
            {'role':'user','channel':'coding','content':'先更新分数变量，再更新界面显示；只改计分，保留其他规则。'},
            {'role':'user','channel':'teaching','content':'我会连续点击两次，确认每次都从上次分数增加。'}]
  t={'id':tid,'title':'教学反思交互验收（隔离夹具）','mode':'opencode','stage':'created','step':0,
     'plan':['实现计分'],'plan_draft':[],'messages':messages,'changes':[],'checks':[]}
  b.teaching.state(t);b.coding_workflow.state(t);s=e.state(t);s['auto']=False
  s['loads'].append({'reply_message_id':1,'code_hash':'fixture','playbook_revision':0,'entries':[{'id':'seed-example','revision':1}],'adoption_verified':False})
  b.save(t)
  observed=[]
  def model(config,system,value):
   if system==e.EVALUATOR:
    return {'observations':[{'dimension':'application','value':1,'reason':'夹具：学生提出修改范围及验证操作',
      'quotes':[{'message_id':2,'quote':messages[2]['content']},{'message_id':3,'quote':messages[3]['content']}]}], 'feedback':[]}
   return {'summary':'验收夹具：具体例子后有修改和验证要求，候选原因仍待验证。','operations':[{
    'type':'add','title':'用状态变化连接显示','when':'学生理解计分状态时','action':'对比同一操作前后的变量及显示。',
    'verify':'观察下次能否独立提出同步修改要求。','limits':'仅当前项目试用，不证明掌握。','tags':['状态'],
    'reason':'夹具模拟候选经验，不是真实学生教学效果。','quotes':[{'message_id':2,'quote':messages[2]['content']}]}]}
  def chat(agent,ctx,progress):
   observed.append(ctx['experience_context'])
   return '验收夹具回复：先对比操作前后的状态和显示。'
  class Handler(b.Handler):
   def log_message(self,*args):pass
   def do_GET(self):
    if self.path in ('/','/index.html'):
     html=(b.ROOT/'frontend/index.html').read_text(encoding='utf8').replace('<head>','<head><script>localStorage.setItem("control-workbench-task",'+json.dumps(tid)+')</script>',1)
     return self.reply(200,html.encode(),'text/html; charset=utf-8')
    return super().do_GET()
  cases=[]
  def step(action,selector=None,**kw):cases.append({'action':action,**({'selector':selector} if selector else {}),**kw})
  step('wait',ms=800);step('assert_count','.teaching .teaching-overview',count=0);step('assert_exists','.teaching #teaching-form');step('click','#open-settings');step('click','#model-timeouts > summary');step('wait',ms=300);step('assert_value','#timeout-teacher_request_seconds',value='60');step('click','#save-model-timeouts');step('wait',ms=300);step('assert_text','#model-timeouts',text='已保存');step('click','#teaching-tools-settings > summary');step('click','#teaching-evolution summary');step('click','#experience-open')
  step('assert_text','#experience-dialog',text='还没有评价')
  step('click','#experience-review');step('wait',ms=1600)
  step('assert_text','#experience-dialog',text='100分');step('assert_text','#experience-dialog',text='局部试用')
  step('click','#experience-dialog > details:first-of-type summary');step('assert_text','#experience-dialog pre',text='保留其他规则')
  step('click','#experience-dialog > button:last-child');step('click','#close-settings')
  step('fill','#teaching-input',value='请继续讲状态的下一步');step('click','#teaching-form .composer-foot button.primary');step('wait',ms=1700)
  step('assert_text','#teaching-messages',text='验收夹具回复');step('click','#open-settings');step('click','#experience-open')
  step('click','#experience-dialog details[data-entry-id^="exp-"] summary')
  step('click','#experience-dialog details[data-entry-id^="exp-"] button:first-of-type');step('wait',ms=500)
  step('assert_text','#experience-dialog details[data-entry-id^="exp-"] summary',text='已停用')
  step('fill','#experience-versions',value='0');step('click','#experience-restore');step('wait',ms=500)
  step('assert_value','#experience-mode',value='observe');step('assert_count','#experience-dialog details[data-entry-id]',count=5)
  step('assert_text','#experience-dialog',text='100分')
  step('click','#experience-dialog > button:last-child');step('click','#close-settings')
  step('assert_count','.teaching .teaching-overview',count=0);step('assert_count','#teaching-form button',count=1)
  with patch.object(e,'call_model',side_effect=model),patch.object(b.teaching,'project_chat',side_effect=chat):
   result=browser_runner.run({}, {},cases,handler=Handler,screenshot=out/'teaching-evolution-ui.png')
  final=b.load(tid)
  used_trial=any(any(row['status']=='trial' for row in packet['entries']) for packet in observed)
  checks={'candidate_reaches_next_teacher':used_trial,'rollback_preserves_review':len(e.state(final)['reviews'])==1,
          'rollback_disables_auto':not e.state(final)['auto'],'source_unchanged':b.read_project_files(tid)=={},
          'next_turn_load_logged':len(e.state(final)['loads'])>=2}
  result.update(kind='isolated_real_browser_teaching_evolution',real_model=False,provider='deterministic_fixture',checks=checks)
  result['passed']=result['passed'] and all(checks.values())
  (out/'teaching-evolution-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps({'passed':result['passed'],'checks':checks,'last_steps':result['results'][-3:]},ensure_ascii=False))
  if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
