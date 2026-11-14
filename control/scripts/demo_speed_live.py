"""One real production-config Teacher call on a synthetic, in-memory project.

No student task or experience changes are saved. No secret/reasoning content logged.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import backend as b
from agents import teaching,project_safety

b.load_host_models()
folder=ROOT/'data/demos'/('speed-live-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
folder.mkdir(parents=True)
t={'id':'isolated-speed-demo','mode':'opencode','title':'模拟点击计分','plan':['理解点击计分'],'plan_draft':[],'step':0,
   'files':{'game.js':'let score = 0;\nfunction addPoint() {\n  score += 1;\n  document.querySelector("#score").textContent = score;\n}'},'changes':[],'checks':[],
   'messages':[{'channel':'coding','role':'user','content':'我想做一个点击按钮加分的小游戏。'},
               {'channel':'coding','role':'assistant','content':'点击按钮调用 game.js 中的 addPoint 更新分数和页面。'},
               {'channel':'teaching','role':'user','content':'解释 game.js:3-4，为什么分数加了一还要再改页面文字？'}]}
with b.connection() as c:b.experience_library.attach(c,t)
started=time.monotonic();events=[]
report={'synthetic_student':True,'production_limits':True,'provider':teaching.TeachingAgent().metadata(),'status':'running'}
def progress(stage,value):
 if not events or events[-1]['stage']!=stage:
  events.append({'stage':stage,'seconds':round(time.monotonic()-started,3)})
  print(json.dumps(events[-1],ensure_ascii=False),flush=True)
try:
 report['reply']=teaching.run(t,progress=progress)
 turn=t['teaching']['turns'][-1]
 report.update(status='completed',timings=turn['request_timings'],requests=turn['request_attempts'],context_usage=turn['context_usage'],experience_context=turn['experience_context'])
except Exception as exc:
 report.update(status='failed',error=str(exc))
finally:
 report.update(elapsed_seconds=round(time.monotonic()-started,3),events=events)
 (folder/'result.json').write_text(json.dumps(project_safety.scrub(report),ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({'status':report['status'],'elapsed_seconds':report['elapsed_seconds'],'path':str(folder/'result.json')},ensure_ascii=False),flush=True)
if report['status']!='completed':raise SystemExit(1)
