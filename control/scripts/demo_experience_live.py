"""Explicit live-model demo with synthetic learner messages in an isolated DB."""
import copy,datetime,json,os,sys,time,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import experience_library as lib,experience_evidence as ev,teaching_evolution as e,teaching


def main():
 b.load_host_models()
 if teaching.TeachingAgent().mode!='model':raise SystemExit('Host Teaching model is not configured')
 output=b.ROOT/'data/demos'/('experience-live-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));output.mkdir(parents=True)
 results={'demo_type':'真实模型、模拟学生对话、隔离数据库','started_at':time.time(),'provider':teaching.TeachingAgent().metadata(),'output':str(output),'experiment_thinking_budget':int(os.environ.get('CONTROL_DEMO_THINKING_BUDGET','2048'))}
 synthetic=[
  {'role':'user','channel':'coding','content':'我想做一个点击按钮加分的小项目。'},
  {'role':'assistant','channel':'coding','content':'已创建score变量、点击处理器和分数显示。'},
  {'role':'user','channel':'teaching','content':'为什么score加1以后还要更新页面？不是已经改了吗？'},
  {'role':'assistant','channel':'teaching','content':'这是状态和渲染的区别。score保存状态，DOM更新渲染，事件处理器先改状态再渲染。'},
  {'role':'user','channel':'teaching','content':'我没学过DOM，渲染也不知道是什么。是不是score一变屏幕就自己变？'},
  {'role':'assistant','channel':'teaching','content':'score是状态，DOM是页面的渲染结果。事件处理器改变状态，然后更新DOM，所以需要渲染。'},
  {'role':'user','channel':'teaching','content':'我还是没听懂，你又说一遍状态和DOM。我现在猜把score改成5，屏幕数字肯定马上变成5，所以后面那句更新文字可以删掉。能先用具体数字和两步变化给我讲吗？'}]
 task={'id':str(uuid.uuid4()),'title':'演示A：点击计分（模拟学生）','mode':'opencode','step':0,'plan':['实现点击计分'],'plan_draft':[],'changes':[],'checks':[],'files':{},'checkpoint_delivery':'manual','messages':synthetic}
 source="let score = 0;\nconst label = document.getElementById('score');\nfunction addPoint() {\n  score += 1;\n  label.textContent = score;\n}\n"
 report=lambda stage,**extra: print(json.dumps({'stage':stage,**extra},ensure_ascii=False),flush=True)
 with patch.object(b,'DATA',output/'workbench'),patch.object(b,'DB',output/'records.sqlite3'):
  b.DATA.mkdir();b.teaching.state(task);b.save(task);b.write_project_file(b.project(task['id'])/'score.js',source)
  task['files']={'score.js':source};task['changes']=[{'file':'score.js','before':'','after':source,'instruction':'实现点击计分'}]
  with b.connection() as c:lib.attach(c,task)
  # Freeze the evidence/rubric and use the normal real evaluator/reflector calls.
  review=ev.enrich(task,e.build_review(task));results['input_messages']=copy.deepcopy(synthetic);results['evidence']=review['evidence'];results['rubric']=review['rubric']
  before=copy.deepcopy(task['teaching_evolution']['entries']);results['initial_count']=len(before)
  def progress(stage,data):
   safe={k:v for k,v in data.items() if k in ('detail','evaluation','scores','reflection')}
   results.setdefault('progress',[]).append({'stage':stage,**copy.deepcopy(safe)})
   if stage=='request':results.setdefault('request_trace',[]).append(data)
   (output/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
   report(stage,detail=data.get('detail'))
  task['_experience_progress']=progress
  started=time.monotonic()
  try:
   original_call=e.call_model
   original_transport=teaching.request_model
   def observe_transport(req,budget,progress):
    response=original_transport(req,budget,progress)
    results.setdefault('transport_outputs',[]).append({'finish_reason':response.get('choices',[{}])[0].get('finish_reason'),'content':response.get('choices',[{}])[0].get('message',{}).get('content'),'usage':response.get('usage')})
    return response
   def capture(config,system,value):
    if os.environ.get('CONTROL_DEMO_THINKING_BUDGET'):
     original_request=teaching.providers.request
     def limited_request(*args,**kwargs):
      req=original_request(*args,**kwargs);payload=json.loads(req.data)
      payload['thinking_budget']=int(os.environ['CONTROL_DEMO_THINKING_BUDGET'])
      req.data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();return req
     with patch.object(teaching.providers,'request',side_effect=limited_request):raw=original_call(config,system,value)
    else:raw=original_call(config,system,value)
    results.setdefault('visible_model_outputs',[]).append({'role':'evaluation' if '独立教学证据评价器' in system else 'reflection','output':b.project_safety.scrub(raw)})
    return raw
   with patch.object(e,'call_model',side_effect=capture),patch.object(teaching,'request_model',side_effect=observe_transport):analyzed=e.analyze(task,review)
   results['evaluation']=analyzed['evaluation'];results['scores']=analyzed['scores'];results['reflection']=analyzed['reflection'];results['evaluation_seconds']=round(time.monotonic()-started,2)
   with b.connection() as c:
    c.execute('BEGIN IMMEDIATE');batch=lib.commit_review(c,task,review,analyzed)
   results['batch']=batch;task.pop('_experience_progress',None);b.save(task);results['after_count']=len(task['teaching_evolution']['entries'])
   new_ids=[x['entry_id'] for x in batch['changes'] if x['before'] is None];results['new_entry_ids']=new_ids;results['committed_operations']=batch['review']['changes']
   report('committed',new_entries=len(new_ids),changes=len(batch['changes']))
   second={'id':str(uuid.uuid4()),'title':'演示B：背包数量（模拟学生）','mode':'opencode','step':0,'plan':['理解数量状态与页面显示'],'plan_draft':[],'files':{},'changes':[],'checks':[],'messages':[{'role':'user','channel':'coding','content':'我想做背包数量按钮，增加一次数量加1。'},{'role':'user','channel':'teaching','content':'我还是分不清状态和页面显示，改了数量为什么还要改文字？不要再重复DOM渲染这些术语，用具体数字和两步变化解释。'}]}
   b.teaching.state(second);b.save(second)
   with b.connection() as c:lib.attach(c,second)
   packet=e.packet(second);results['next_project_context']=packet
   report('next_project_teaching',focus=(packet.get('validation_focus') or {}).get('entry_id'))
   (output/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
   second_start=time.monotonic();reply=teaching.run(second,'message',lambda stage,detail:None);results['next_teacher_reply']=reply;results['next_teacher_seconds']=round(time.monotonic()-second_start,2)
   results['next_teacher_trace']=second['teaching']['turns'][-1]
   if batch['changes']:
    with b.connection() as c:
     c.execute('BEGIN IMMEDIATE');current=lib.read(c);lib.manage(c,{'expected_revision':current['revision'],'action':'undo','batch_id':batch['id']});lib.attach(c,second)
    results['context_after_undo']=e.packet(second)
    results['undo_excludes_new_entries']=not any(r['id'] in new_ids for r in results['context_after_undo']['entries']);results['undo_performed']=True
   results['status']='completed'
  except Exception as exc:
   task.pop('_experience_progress',None);results['status']='failed';results['failure']=b.background_error(exc);report('failed',error=results['failure'])
  finally:
   results['finished_at']=time.time();(output/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
   report('finished',status=results['status'],result_file=str(output/'result.json'))
 if results['status']!='completed':raise SystemExit(1)

if __name__=='__main__':main()
