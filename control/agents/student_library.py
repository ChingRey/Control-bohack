"""Explicit local learner identities; no automatic cross-student import."""
import json
import uuid
from . import workflow_records, workflow

def initialize(conn):
 conn.execute('CREATE TABLE IF NOT EXISTS student_libraries (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
def read(conn,student_id):
 row=conn.execute('SELECT body FROM student_libraries WHERE id=?',(student_id,)).fetchone()
 if not row:raise ValueError('本地学习者不存在')
 return json.loads(row[0])
def write(conn,record):conn.execute('INSERT OR REPLACE INTO student_libraries VALUES (?,?)',(record['id'],json.dumps(record,ensure_ascii=False)))
def create(conn,name):
 if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('学习者名称需1至80字')
 record={'id':str(uuid.uuid4()),'name':name.strip(),'revision':0,'rules':[],'profile':[]};write(conn,record);return record
def attach(conn,task,body):
 if body.get('confirmed') is not True:raise ValueError('请明确选择是否载入个人经验')
 record=read(conn,body.get('student_id'));s=workflow_records.initialize(task)
 if s.get('student_id') and s['student_id']!=record['id']:raise ValueError('已有学习者关联，请新建项目切换学习者')
 s['student_id']=record['id']
 imported=s.setdefault('imported_rule_versions',[])
 for rule in record['rules']:
  key=rule['id']+':'+str(rule['revision'])
  if key in imported or rule['status']!='active':continue
  previous=next((r for r in s['rules'] if r.get('origin_student_rule_id')==rule['id']),None)
  if previous:
   previous['history'].append({k:v for k,v in previous.items() if k!='history'})
   previous.update({k:v for k,v in rule.items() if k not in ('id','history')});imported.append(key);continue
  if len(workflow_records.active_rules(task))>=15:break
  local={**rule,'id':str(uuid.uuid4()),'origin_student_rule_id':rule['id'],'source':'explicit_personal_import','history':[],'verified':False}
  s['rules'].append(local);imported.append(key)
 s['prior_learning_observations']=record['profile'][-10:];s['revision']+=1
 return record
def promote(conn,task,body):
 s=workflow_records.initialize(task)
 if body.get('confirmed') is not True or not s.get('student_id'):raise ValueError('请先选择学习者并明确确认通用经验留存')
 record=read(conn,s['student_id']);ids=body.get('rule_ids')
 if not isinstance(ids,list) or len(ids)>15:raise ValueError('规则列表无效')
 chosen=[r for r in s['rules'] if r['id'] in ids and r['status']=='active']
 if len(chosen)!=len(set(ids)):raise ValueError('只能留存本项目的有效规则')
 for rule in chosen:
  old=next((r for r in record['rules'] if r.get('source_project')==task['id'] and r.get('source_rule')==rule['id']),None)
  if old and old['source_revision']==rule['revision']:continue
  if old:
   old.setdefault('history',[]).append({k:v for k,v in old.items() if k!='history'})
   target=old
  else:
   if len([r for r in record['rules'] if r['status']=='active'])>=15:raise ValueError('个人通用经验最多15条，请先停用旧规则')
   target={'id':str(uuid.uuid4()),'revision':0,'history':[]};record['rules'].append(target)
  target.update({k:rule[k] for k in ('title','content','when','limits','status')})
  target.update(revision=target['revision']+1,source_project=task['id'],source_rule=rule['id'],source_revision=rule['revision'],verified=False,evidence_ids=[],quotes=[])
 if body.get('include_profile') is True:
  record['profile'].append({'source_project':task['id'],'concepts':s['concepts'],'notes':s['materials']['learner'][-1:],'verified_mastery':False})
 record['revision']+=1;write(conn,record);return record
