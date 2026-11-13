import json,time,urllib.request
from pathlib import Path
BASE='http://127.0.0.1:8774/api'
def api(p,b=None):
 with urllib.request.urlopen(urllib.request.Request(BASE+p,data=None if b is None else json.dumps(b).encode(),headers={'Content-Type':'application/json'}),timeout=15) as r:return json.load(r)
out=Path('docs/experiments/coding-baseline');out.mkdir(parents=True,exist_ok=True)
r={'health':api('/health'),'scope':'two small deterministic programming tasks, not project-level benchmark','trials':[]}
cases=[('money','请直接编写core.js，把函数挂在globalThis上。实现total(items)：items为{price:十进制价格字符串,quantity:非负整数}数组，返回精确的整数分总额。价格最多两位小数，允许0；非法价格或数量抛Error。不允许修改输入。使用纯JS，无依赖。此消息授权完成这个小任务，不必讨论计划。'),('todos','请直接编写core.js，把createStore挂在globalThis上。createStore()返回{add(title),remove(id),list()}。title去首尾空白后不能为空，否则抛Error；add返回正整数id；删除已有条目后新增id不能复用；list返回{id,title}数组且外部修改不能影响内部状态。使用纯JS，无依赖。此消息授权完成这个小任务，不必讨论计划。')]
for name,prompt in cases:
 t=api('/tasks',{'coding_mode':'opencode'});tid=t['id'];api('/tasks/'+tid+'/coding/messages',{'message':prompt})
 for i in range(200):
  time.sleep(1);t=api('/tasks/'+tid)
  if t.get('coding_run',{}).get('status') not in ('running','queued'):break
 r['trials'].append({'name':name,'task_id':tid,'prompt':prompt,'run':t.get('coding_run'),'files':t['files'],'messages':t['messages'],'events':t.get('coding_workflow',{}).get('tool_events',[])})
 (out/'raw.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(name,t.get('coding_run'),list(t['files']),flush=True)
