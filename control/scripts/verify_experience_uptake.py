"""Paired live experience uptake probe; synthetic preference, not competence eval."""
import sys,json,time,urllib.request,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend
from agents import learning
BASE='http://127.0.0.1:8774/api'
def api(route,body=None):
 req=urllib.request.Request(BASE+route,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
root=Path(__file__).resolve().parents[1]/'docs/experiments/experience-uptake';root.mkdir(parents=True,exist_ok=True)
health=api('/health');assert health['coding']['configured']
report={'model':health['coding']['model'],'scope':'synthetic project preference uptake, not ability improvement','runs':[]}
prompt='请直接实现一个静态网页计数器，有加一和重置按钮，刷新后保留数值。使用index.html、app.js、style.css，需求已明确，这次授权完成全部这个小任务。不需要先讨论。'
for n,enabled in enumerate([False,True,True,False]):
 t=api('/tasks',{'coding_mode':'opencode'});tid=t['id'];t=backend.load(tid)
 s=learning.state(t);s['experiences'].append({'id':'synthetic-storage-convention','revision':1,'status':'confirmed','kind':'preference','title':'实验用存储键约定','when':'计数器持久化','rule':'计数器的localStorage存储键统一使用classroom-counter-v1。','verification':'检查实际写入与读取均使用该键','limits':'仅本实验的计数器项目，不代表通用规则','tags':['计数器'],'source':'synthetic_experiment_not_student_evidence'})
 s['revision']+=1;backend.save(t)
 api('/tasks/'+tid+'/coding/capabilities',{'experience_enabled':enabled})
 before=api('/tasks/'+tid)['files'];api('/tasks/'+tid+'/coding/messages',{'message':prompt})
 for _ in range(200):
  time.sleep(1);t=api('/tasks/'+tid)
  if t.get('coding_run',{}).get('status') not in ('running','queued'):break
 files=t.get('files',{});contains=[name for name,body in files.items() if 'classroom-counter-v1' in body]
 row={'trial':n+1,'experience_enabled':enabled,'task_id':tid,'initial_files':before,'run':t.get('coding_run'),'files':files,'expected_key_files':contains,'load_record':t.get('coding_workflow',{}).get('loads',[]),'assistant_output':[m['content'] for m in t['messages'] if m['channel']=='coding' and m['role']=='assistant'],'tool_events':t.get('coding_workflow',{}).get('tool_events',[])}
 report['runs'].append(row);(root/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'trial':n+1,'enabled':enabled,'status':row['run']['status'],'key_files':contains},ensure_ascii=False),flush=True)
print('REPORT',root/'results.json',flush=True)
