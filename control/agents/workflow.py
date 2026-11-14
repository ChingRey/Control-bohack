"""Versioned project materials and recoverable file snapshots; no model approval gate."""
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone

STAGES=['定义作品','看懂原型','逐项开发与验证','独立扩展','交付']
MATERIALS=('requirements','design','experiences','coverage','learner')
def state(task):
 return task.setdefault('workflow',{'revision':0,'stage':0,'feature':'','materials':{name:[] for name in MATERIALS},'events':[]})
def shared(task):
 s=state(task)
 return {'baseline_rules':[{'id':'preserve-unrelated-files','content':'保留与本轮目标无关的文件和数据；删除或重命名需与已授权任务有关，不靠清空项目修复。','source':'application_baseline'},{'id':'truthful-verification','content':'工具真实写入后才说完成；没运行的测试明确写未运行。','source':'application_baseline'}],'revision':s['revision'],'stage':STAGES[s['stage']],'materials':{n:s['materials'][n][-1:] for n in MATERIALS[:3]},'confirmed_materials':{n:next((v for v in reversed(s['materials'][n]) if v['status']=='confirmed'),None) for n in MATERIALS[:3]}}
def update(task,body,actor='student'):
 s=state(task)
 if body.get('expected_revision')!=s['revision']:raise ValueError('流程版本已变化，请刷新后重试')
 kind=body.get('kind')
 if kind not in MATERIALS:raise ValueError('未知材料')
 content=body.get('content')
 if not isinstance(content,str) or len(content)>20000:raise ValueError('材料应为不超过20000字的文本')
 if body.get('confirmed') and actor!='student':raise ValueError('Agent只能生成草稿，学生确认材料')
 s['revision']+=1
 entry={'revision':s['revision'],'content':content,'status':'confirmed' if body.get('confirmed') else 'draft','actor':actor}
 s['materials'][kind].append(entry)
 s['events'].append({'kind':kind,'revision':s['revision'],'actor':actor})
 return entry
def digest(files,assets):
 return hashlib.sha256(json.dumps([files,assets],sort_keys=True).encode()).hexdigest()
def capture(task,files,assets,label):
 versions=task.setdefault('project_versions',[])
 record={'id':str(uuid.uuid4()),'label':label,'created_at':datetime.now(timezone.utc).isoformat(),'hash':digest(files,assets),'files':copy.deepcopy(files),'assets':copy.deepcopy(assets)}
 versions.append(record)
 return record
def summary(task):
 return [{k:v[k] for k in ('id','label','created_at','hash')} for v in task.get('project_versions',[])]
