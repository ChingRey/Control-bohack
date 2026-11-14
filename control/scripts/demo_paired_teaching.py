"""Real model paired generation on identical compact experimental context."""
import copy,json,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend as b
from agents import teaching,teaching_evolution as e,model_limits

def main():
 b.load_host_models();folder=Path(sys.argv[1]) if len(sys.argv)>1 else max((b.ROOT/'data/demos').glob('experience-live-*'),key=lambda p:p.stat().st_mtime)
 with b.connection() as c:book=b.experience_library.read(c)
 # A pre-existing explicit lesson hypothesis; no new experience is fabricated.
 entry=next(row for row in book['entries'] if row['id']=='seed-example')
 entry2=next(row for row in book['entries'] if row['id']=='preset-trace')
 question='我在做背包数量加1的按钮。你之前说变量是状态、页面是渲染，我听不懂。为什么数量变量加1以后，还要单独更新页面文字？'
 context={'action':'message','interaction_mode':'project_chat','files':{},'project_files':{'files':[]},
   'messages':[{'id':0,'channel':'teaching','role':'user','content':question}],
   'current_request':{'message_id':0},'student_evidence':[{'id':0}],
   'development_scope':{'current_title':'理解按钮如何改变数量和显示'},'continuity_memory':{},
   'context_usage':{'loaded_message_ids':[0]},'code_hash':'demo-no-code',
   'teaching_intent':{'objective':'回答当前学生问题；不要编造实际代码或运行结果'},
   'experience_context':{'revision':book['revision'],'mode':'adaptive','entries':[{k:v for k,v in x.items() if k in ('id','revision','title','when','action','verify','limits','status')} for x in (entry,entry2)],
   'validation_focus':{'entry_id':entry['id'],'entry_revision':entry['revision'],'hypothesis':entry['action'],'observe':entry['verify'],
    'instruction':'本轮优先尝试具体例子先行；用同一次操作前后的数量与显示变化解释，不声称学生已理解。'}}}
 comparison={'model':teaching.TeachingAgent().metadata(),'synthetic_learner':True,'source_result':str(folder/'result.json'),
   'experience_packet':context['experience_context'],'question':question,
   'experiment_limits':{'max_output_tokens':600,'thinking_budget':512,'max_attempts':1,'total_seconds_per_arm':90},
   'notice':'真实模型；同一份精简实验上下文，仅切换经验。两侧统一限制输出600/推理512；不是完整线上上下文。单次非重复实验，不能证明因果或学生学习效果。'}
 original_request=teaching.providers.request
 def bounded(config,messages,max_tokens,*args,**kwargs):
  kwargs['tools']=None
  req=original_request(config,messages,600,*args,**kwargs)
  payload=json.loads(req.data);payload['thinking_budget']=512
  req.data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
  return req
 for key,enabled in [('without_experience',False),('with_experience',True)]:
  ctx=copy.deepcopy(context)
  if not enabled:ctx['experience_context']={'revision':book['revision'],'mode':'off','entries':[],'validation_focus':None}
  agent=teaching.TeachingAgent();agent.history=ctx['messages'];agent.project_source={};agent.request_budget=model_limits.budget('teacher');agent.request_budget.update(max_attempts=1,deadline=time.monotonic()+90,total_timeout=90,request_timeout=60)
  start=time.monotonic();print(json.dumps({'stage':key,'status':'running'},ensure_ascii=False),flush=True)
  try:
   with patch.object(teaching.providers,'request',side_effect=bounded):comparison[key]=teaching.project_chat(agent,ctx,lambda *a:None)
   comparison[key+'_seconds']=round(time.monotonic()-start,2);comparison[key+'_trace']=agent.request_budget.get('requests',[])
  except Exception as exc:comparison[key+'_error']=b.background_error(exc)
  (folder/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'stage':key,'seconds':comparison.get(key+'_seconds'),'error':comparison.get(key+'_error')},ensure_ascii=False),flush=True)
 comparison['status']='completed' if comparison.get('with_experience') and comparison.get('without_experience') else 'incomplete'
 (folder/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':comparison['status'],'file':str(folder/'comparison.json')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
