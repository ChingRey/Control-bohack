"""Actual browser UI acceptance against an isolated DB. No real models or student data."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import browser_runner,workflow_records as wr

def main():
 output=b.ROOT/'data'/'verification';output.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as temp,patch.object(b,'DATA',Path(temp)),patch.object(b,'DB',Path(temp)/'records.sqlite3'),patch.dict(os.environ,{'TEACHING_MODE':'sample'}):
  import uuid
  tid=str(uuid.uuid4());task={'id':tid,'title':'Isolated UI Acceptance','mode':'opencode','stage':'created','step':0,'plan':[],'plan_draft':[],'messages':[{'channel':'coding','role':'user','content':'Preserve existing data'}],'changes':[],'checks':[],'checkpoint_delivery':'manual'}
  b.teaching.state(task);b.coding_workflow.state(task);wr.initialize(task)
  proposal={'kind':'rule','title':'Preserve data','content':'Do not change stored data when editing the UI','when':'Presentation changes','limits':'Schema migrations are separate','evidence_ids':[0],'quotes':[{'message_id':0,'quote':'Preserve existing data'}]}
  wr.candidates(task,{'items':[proposal]},[0]);b.save(task)
  original='<!doctype html><html><body><button id="counter">0</button></body></html>'
  b.write_project_file(b.project(tid)/'index.html',original)
  class Handler(b.Handler):
   def log_message(self,*args):pass
   def do_GET(self):
    if self.path in ('/','/index.html'):
     html=(b.ROOT/'frontend/index.html').read_text(encoding='utf-8').replace('<head>','<head><script>localStorage.setItem("control-workbench-task",'+json.dumps(tid)+')</script>',1)
     return self.reply(200,html.encode(),'text/html; charset=utf-8')
    return super().do_GET()
  cases=[]
  def step(action,selector=None,**kwargs):cases.append({'action':action,**({'selector':selector} if selector else {}),**kwargs})
  def wait(ms=300):step('wait',ms=ms)
  wait(600);step('assert_exists','#project-materials');step('assert_exists','#flow-next')
  step('click','#project-materials');step('fill','#workflow-content',value='A single visible counter. Acceptance: starts at zero.')
  step('click','#workflow-confirm');wait();step('assert_text','#workflow-material-status',text='学生已确认');step('click','#workflow-dialog button[onclick]')
  step('click','#flow-review');step('fill','#flow-proposals textarea',value='Preserve existing storage keys and records during UI-only changes')
  step('click','#flow-proposals section button');wait();step('assert_text','#flow-rules',text='storage keys')
  step('fill','#flow-feature-title',value='Show a visible counter');step('click','#flow-feature-create');wait();step('click','#flow-review-dialog button[onclick]')
  step('click','#flow-student');wait();step('fill','#flow-student-name',value='UI Learner');step('click','#flow-student-create');wait();step('click','#flow-student-attach');wait()
  step('click','#flow-promote-rules input');step('click','#flow-promote');wait();step('click','#flow-student-dialog button[onclick]')
  step('click','#flow-delivery');step('fill','#flow-browser-steps select',value='assert_text');step('fill','#flow-browser-steps input',value='#counter');step('fill','#flow-browser-steps input:nth-of-type(2)',value='0')
  step('click','#flow-browser-run');wait(3000);wait(1000);step('assert_text','#flow-verification',text='real_chromium_browser')
  step('fill','#flow-how-run',value='Serve index.html from a static HTTP server');step('fill','#flow-tested',value='Real browser verified counter begins at zero');step('fill','#flow-limits',value='Static prototype; no editing or backend')
  step('click','#flow-delivery-prepare');wait();step('assert_exists','#flow-delivery-download:not([hidden])');step('click','#flow-delivery-dialog button[onclick]')
  # A second pass exercises source save and recoverable versions; the first pass stays under 50 steps.
  result=browser_runner.run({}, {},cases,handler=Handler,screenshot=output/'workflow-ui.png',accept_dialogs=True)
  second=[]
  def more(action,selector=None,**kwargs):second.append({'action':action,**({'selector':selector} if selector else {}),**kwargs})
  more('wait',ms=500);more('click','#flow-review');more('fill','#flow-feature-explanation',value='The counter display remains unchanged; initial zero was verified in the real browser.')
  more('click','#flow-feature-accept');more('wait',ms=300);more('assert_text','#flow-features',text='accepted');more('click','#flow-review-dialog button[onclick]')
  more('click','#project-versions');more('click','#version-save');more('wait',ms=300);more('click','#versions-dialog button[onclick]')
  more('fill','#code',value='<!doctype html><body><h1>changed</h1></body>');more('click','#save');more('wait',ms=300)
  more('click','#project-versions');more('click','#versions-list p:first-child button');more('wait',ms=400);more('click','#versions-dialog button[onclick]');more('assert_value','#code',value=original)
  recovered=browser_runner.run({}, {},second,handler=Handler,screenshot=output/'workflow-restored.png',accept_dialogs=True)
  result['feature_and_restore_ui_passed']=recovered['passed'];result['passed']=result['passed'] and recovered['passed']
  if not recovered['passed']:result['recovery_failure']=recovered['results'][-1]
  third=[{'action':'wait','ms':500},{'action':'assert_count','selector':'#teaching-library-choice option','count':21},
   {'action':'click','selector':'#open-lesson-cards'},
   {'action':'wait','ms':500},
   {'action':'assert_exists','selector':'#lesson-card-dialog[open] section'},
   {'action':'click','selector':'#lesson-card-dialog button:last-child'},
   {'action':'fill','selector':'#teaching-library-choice','value':'L09'},{'action':'click','selector':'#teaching-library-learn'},
   {'action':'wait','ms':1500},{'action':'click','selector':'#teaching-references summary'},
   {'action':'assert_text','selector':'#teaching-reference-list','text':'localStorage'},
   {'action':'assert_text','selector':'#teaching-reference-list','text':'未提交模型'},
   {'action':'assert_exists','selector':'#teaching-reference-list a[href^="https://developer.mozilla.org/"]'}]
  selected=browser_runner.run({}, {},third,handler=Handler,screenshot=output/'teaching-library-ui.png')
  result['teaching_library_ui_passed']=selected['passed'];result['passed']=result['passed'] and selected['passed']
  if not selected['passed']:result['teaching_library_failure']=selected['results'][-1]
  settings_cases=[{'action':'wait','ms':500},{'action':'click','selector':'#settings'},
   {'action':'fill','selector':'#provider-choice','value':'siliconflow'},
   {'action':'assert_value','selector':'#endpoint','value':'https://api.siliconflow.cn/v1/chat/completions'},
   {'action':'assert_value','selector':'#model-choice','value':'zai-org/GLM-5.3'},
   {'action':'assert_text','selector':'#provider-note','text':'硅基流动'},
   {'action':'fill','selector':'#api-key','value':'fixture-browser-key'},
   {'action':'fill','selector':'#provider-choice','value':'deepseek'},
   {'action':'assert_value','selector':'#api-key','value':''},
   {'action':'click','selector':'#coding-settings'},
   {'action':'assert_value','selector':'#coding-provider','value':'siliconflow'},
   {'action':'assert_value','selector':'#coding-model','value':'Qwen/Qwen3-Coder-30B-A3B-Instruct'},
   {'action':'assert_exists','selector':'#coding-region-label[hidden]'},
   {'action':'fill','selector':'#coding-provider','value':'bailian'},
   {'action':'assert_exists','selector':'#coding-region-label:not([hidden])'},
   {'action':'click','selector':'#coding-settings-close'}]
  settings_result=browser_runner.run({}, {},settings_cases,handler=Handler,screenshot=output/'siliconflow-settings-ui.png')
  result['siliconflow_settings_ui_passed']=settings_result['passed'];result['passed']=result['passed'] and settings_result['passed']
  if not settings_result['passed']:result['siliconflow_settings_failure']=settings_result['results'][-1]
  final=b.load(tid);result.update(kind='isolated_workbench_ui_acceptance',real_model=False,proposal_origin='test_fixture',materials_confirmed=bool(final['workflow']['materials']['requirements']),rule_count=len(wr.active_rules(final)),browser_record_count=len(final.get('browser_records',[])),delivery_prepared=bool(final.get('delivery_report')))
  (output/'workflow-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({k:v for k,v in result.items() if k not in ('results',)},ensure_ascii=False))
  if not result['passed']:print(json.dumps(result['results'][-2:],ensure_ascii=False));return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
