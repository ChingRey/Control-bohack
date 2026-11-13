"""Local Control workbench: sample coding, configurable teaching, SQLite records."""
import argparse
import json
import mimetypes
import os
import sqlite3
import socket
import threading
import uuid
import time
import tempfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from agents import teaching, memory, learning, knowledge, providers, coding_workflow, opencode_executor, code_refs, project_files, checkpoint_control, checkpoints as checkpoint_events
from agents.coding import PLAN, FILES, SampleCodingAgent

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'workbench'
DATA.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
TASK_LOCKS = {}
DB = DATA / 'records.sqlite3'

def task_lock(key):
 with LOCK:
  return TASK_LOCKS.setdefault(key, threading.RLock())

@contextmanager
def connection():
 c = sqlite3.connect(DB)
 try:
  c.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS teaching_history (task_id TEXT, kind TEXT, record_id TEXT, body TEXT NOT NULL, PRIMARY KEY(task_id,kind,record_id))')
  c.execute('CREATE TABLE IF NOT EXISTS learning_versions (task_id TEXT, revision TEXT, digest TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(task_id,revision))')
  knowledge.initialize(c)
  yield c
  c.commit()
 except Exception:
  c.rollback()
  raise
 finally:
  c.close()

def save(t):
 with connection() as c:
  s=t.get('teaching',{});course=s.get('course',{})
  collections=[('turn',s.get('turns',[]),20,'id'),('checkpoint',course.get('checkpoints',[]),40,'turn')]
  collections.extend(('observation:'+g['id'],g.get('observations',[]),20,'turn') for g in course.get('objectives',[]))
  for kind,records,keep,id_field in collections:
   if len(records)>keep:
    for record in records[:-keep]:
     c.execute('INSERT OR IGNORE INTO teaching_history VALUES (?,?,?,?)',(t['id'],kind,str(record[id_field]),json.dumps(record,ensure_ascii=False)))
    del records[:-keep]
  if s.get('memory'):
   import hashlib
   value={'memory':s['memory'],'course_notes':{'summary':course.get('summary',''),'resume_note':course.get('resume_note','')},'learning':s.get('learning',{})}
   body=memory.encoded(value);digest=hashlib.sha256(body.encode()).hexdigest()
   revision=f"{s['memory']['revision']}:{s.get('learning',{}).get('revision',0)}"
   old=c.execute('SELECT digest FROM learning_versions WHERE task_id=? AND revision=?',(t['id'],revision)).fetchone()
   if old and old[0]!=digest:raise ValueError('学习记录版本冲突，拒绝覆盖旧版本')
   c.execute('INSERT OR IGNORE INTO learning_versions VALUES (?,?,?,?)',(t['id'],revision,digest,body))
  knowledge.sync_task(c,t)
  c.execute('INSERT OR REPLACE INTO tasks VALUES (?,?)', (t['id'], json.dumps(t, ensure_ascii=False)))

def load(tid):
 with connection() as c:
  row = c.execute('SELECT body FROM tasks WHERE id=?', (tid,)).fetchone()
 if not row: raise ValueError('任务不存在')
 return json.loads(row[0])

def project(tid):
 p = DATA / tid / 'project'; p.mkdir(parents=True, exist_ok=True); return p

def snapshot(t):
 t['files'] = read_project_files(t['id'])
 t['file_hashes']={name:code_refs.digest(source) for name,source in t['files'].items()}
 if t.get('mode')=='opencode':
  coding_workflow.state(t)
  if not t.get('plan_draft'):
   for m in reversed(t.get('messages',[])):
    if m.get('channel')=='coding' and m.get('role')=='assistant' and coding_workflow.sync_plan(t,m.get('content','')):break
 t['coding_provider']={'framework':'opencode' if t.get('mode')=='opencode' else 'sample',**opencode_executor.metadata()}
 t['teaching_provider'] = teaching.TeachingAgent().metadata()
 teaching.state(t)
 t['knowledge_topics']=teaching.KNOWLEDGE
 t['learning_overview']={'profile':learning.profile(t),'skills':learning.readiness(t)}
 with connection() as c:t['project_knowledge']=knowledge.list_task(c,t['id'])
 t['preview_url']=f'http://127.0.0.1:{PREVIEW_PORT}/preview/{t["id"]}/index.html' if PREVIEW_PORT else f'/preview/{t["id"]}/index.html'
 return t

def task_signature(t):
 fields=('messages','changes','plan','plan_draft','step','teaching','checks','runtime_observations')
 return json.dumps({key:t.get(key) for key in fields},sort_keys=True,ensure_ascii=False)

def read_project_files(tid):
 return project_files.read(project(tid))

def write_project_file(path,content):
 # Encode before opening anything, then replace atomically: failed writes keep the old file.
 raw=content.encode('utf-8');temporary=None
 path.parent.mkdir(parents=True,exist_ok=True)
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as stream:
   temporary=Path(stream.name);stream.write(raw);stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,path)
 finally:
  if temporary is not None and temporary.exists():temporary.unlink()

def apply_coding_files(task, before, after, instruction):
 touched=[];changes=[]
 try:
  for name in sorted(set(before)|set(after)):
   if before.get(name)==after.get(name):continue
   path=project_files.target(project(task['id']),name)
   touched.append(name)
   if name in after:write_project_file(path,after[name])
   else:path.unlink()
   changes.append(dict(file=name,before=before.get(name,''),after=after.get(name,''),deleted=name not in after,instruction=instruction))
 except Exception:
  rollback_failed=False
  for name in reversed(touched):
   try:
    path=project_files.target(project(task['id']),name)
    if name in before:write_project_file(path,before[name])
    elif path.exists():path.unlink()
   except OSError:rollback_failed=True
  if rollback_failed:raise ValueError('部分文件恢复失败，请核对项目文件') from None
  raise
 task['changes'].extend(changes)

def start_teaching(t, action='message'):
 if t.get('teaching_run',{}).get('status') in ('queued','running'): raise ValueError('教师正在处理上一条消息')
 teaching.state(t)
 job={'id':str(uuid.uuid4()),'status':'queued','detail':'消息已保存，等待教师处理','started_at':time.time()}
 if action in ('checkpoint','review') and t.get('coding_checkpoints'):
  checkpoint=t['coding_checkpoints'][-1]
  job['checkpoint_id']=checkpoint['checkpoint_id']
  checkpoint['delivery']={'status':'queued','teaching_run_id':job['id']}
 t['teaching_run']=job;save(t)
 baseline=task_signature(t);work=json.loads(json.dumps(t));base_count=len(t['messages'])
 def worker():
  source_files=None
  def progress(stage,detail):
   with task_lock(work['id']):
    fresh=load(work['id'])
    if fresh.get('teaching_run',{}).get('id')!=job['id']: raise ValueError('本次教师任务已被替换')
    fresh['teaching_run'].update(status='running',stage=stage,detail=detail)
    save(fresh)
  try:
   progress('reading','正在读取当前代码与学习记录')
   snapshot(work);source_files=work['files'].copy()
   reply=teaching.run(work,action,progress)
   message(work,'teaching','assistant',reply)
   result={'status':'completed','detail':'回复已完成'}
  except Exception as e:
   detail=str(e) if isinstance(e,ValueError) else '处理出现异常，请重试'
   result={'status':'failed','detail':'本次回复未完成，你的消息已保存，可重试','error':detail}
  # Only the current job may update its fields; never write an old whole-task snapshot.
  with task_lock(work['id']):
   fresh=load(work['id'])
   if fresh.get('teaching_run',{}).get('id')!=job['id']: return
   stale=task_signature(fresh)!=baseline
   try: stale=stale or (source_files is not None and read_project_files(work['id'])!=source_files)
   except (OSError,UnicodeError): stale=True
   if stale:
    result={'status':'failed','detail':'项目或学习记录已变化，本次分析已过期，请重新审查','error':'stale_context'}
   elif result['status']=='completed':
    fresh['messages'].extend(work['messages'][base_count:])
    fresh['teaching']=work['teaching']
   if not stale and result['status']=='failed' and work['teaching']['memory']['revision']>fresh['teaching']['memory']['revision']:
    fresh['teaching']['memory']=work['teaching']['memory']
   if job.get('checkpoint_id'):
    for checkpoint in fresh.get('coding_checkpoints',[]):
     if checkpoint['checkpoint_id']==job['checkpoint_id']:
      checkpoint['delivery'].update(status=result['status'],error=result.get('error'))
   fresh['teaching_run'].update(result,elapsed_seconds=round(time.time()-job['started_at'],1))
   if result['status']=='failed': teaching.state(fresh)['last_error']=result['error']
   save(fresh)
 threading.Thread(target=worker,daemon=True).start()

def start_checkpoint_teaching(t):
 # Coding is already committed. A Teaching failure must not rewrite its status.
 if t.get('checkpoint_delivery')=='manual':
  t['coding_checkpoints'][-1]['delivery']={'status':'available','mode':'manual'};save(t);return
 try:
  start_teaching(t,'checkpoint')
 except Exception as e:
  detail=str(e) if isinstance(e,ValueError) else '教师检查点启动失败，请重新审查'
  t['teaching_run']={'id':str(uuid.uuid4()),'status':'failed','detail':'开发已保存，教师检查点未完成；可重新审查',
                     'error':detail,'checkpoint_id':t['coding_checkpoints'][-1]['checkpoint_id']}
  t['coding_checkpoints'][-1]['delivery']={'status':'failed','error':detail}
  save(t)

def message(t, channel, role, content):
 entry=dict(channel=channel, role=role, content=content)
 if channel=='teaching' and role=='assistant': entry['engine']=teaching.TeachingAgent().mode
 t['messages'].append(entry)


def start_coding(t, instruction, planning=False, chatting=False, checkpoint_operation=None):
 if not opencode_executor.metadata()['configured']:raise ValueError('请先连接Coding模型')
 if not opencode_executor.binary():raise ValueError('OpenCode尚未安装')
 job={'id':str(uuid.uuid4()),'status':'running','detail':'Coding Agent正在处理当前阶段…','started_at':time.time()}
 if checkpoint_operation is not None:
  job['checkpoint_operation']={'checkpoint_id':checkpoint_operation['root_checkpoint_id'],'request_id':checkpoint_operation['request_id']}
  job['skill_results']=checkpoint_operation['skill_results']
  checkpoint_operation.update(status='running',coding_run_id=job['id'])
 t['coding_run']=job;save(t)
 work=json.loads(json.dumps(t));original=read_project_files(t['id']);signature=task_signature(t)
 with connection() as c:knowledge_context=knowledge.search(c,t['id'],instruction,knowledge.code_hash(original)) if t.get('knowledge_enabled',True) else []
 packet=coding_workflow.prepare(work,instruction,learning.coding_packet(work,instruction),knowledge_context)
 if not chatting:
  packet.pop('plan',None)
  packet['authorized_phase']=t['plan'][t['step']] if t.get('plan') and t['step']<len(t['plan']) else instruction
  packet['execution_boundary']='仅执行authorized_phase；不得推进其他阶段，不得修改已确认计划。完成后停止等待学生检查。'
 if chatting:
  packet={'student_message':instruction,'learning_context':packet['learning_context'],'project_knowledge':knowledge_context,'locked_plan':bool(t.get('plan')),'authorized_phase':t['plan'][t['step']] if t.get('plan') and t['step']<len(t['plan']) else None}
 if checkpoint_operation is not None:packet['skill_unlock_notifications']=checkpoint_operation['skill_results']
 packet['recent_dialogue']=[{'role':m['role'],'content':m['content'][:4000]} for m in work['messages'] if m['channel']=='coding'][-12:]
 def worker():
  try:
   if not chatting:packet['recent_dialogue']=[]
   result=opencode_executor.execute(original,packet,planning or chatting,chatting)
   with task_lock(t['id']):
    fresh=load(t['id'])
    if fresh.get('coding_run',{}).get('id')!=job['id']:return
    if task_signature(fresh)!=signature or read_project_files(t['id'])!=original:raise ValueError('项目已变化，拒绝采用过期结果')
    if chatting:
     if fresh.get('plan') and any(result['files'].get(n)!=original.get(n) for n in result['files']):
      coding_workflow.state(fresh)['checkpoints'][fresh['step']]['status']='executed_pending_review'
     coding_workflow.sync_plan(fresh,result['text'],result['events'])
     apply_coding_files(fresh,original,result['files'],instruction)
    elif planning:
     if not coding_workflow.sync_plan(fresh,result['text'],result['events']):
      if not fresh.get('plan_draft'):raise ValueError('尚未形成可同步的计划，请继续讨论阶段和验收点')
    else:
     apply_coding_files(fresh,original,result['files'],instruction)
     coding_workflow.state(fresh)['checkpoints'][fresh['step']]['status']='executed_pending_review'
     fresh['stage']='review'
    w=coding_workflow.state(fresh);w['status']='paused';w['tool_events']=result['events']
    w['loads'].append({'phase':work['step'],'rule_versions':[{'id':r['id'],'revision':r['revision']} for r in packet['learning_context']['rules']],'knowledge_versions':[{'id':r['id'],'revision':r['revision'],'code_hash':r['code_hash']} for r in packet.get('project_knowledge',[])],'skill_versions':[],'submitted':True,'applied':False})
    coding_workflow.event(fresh,'turn_finished','OpenCode轮次结束；等待学生审查与确认，未验证行为正确性')
    message(fresh,'coding','assistant',result['text']);fresh['messages'][-1]['code_refs']=code_refs.collect(result['text'],result['files']);fresh['coding_run'].update(status='completed',detail='已暂停，等待审查')
    if not chatting:
     checkpoint=checkpoint_events.record(fresh,job['id'],instruction,result['text'],original,result['files'],work['step'],'planning' if planning else 'development',result.get('events',[]))
     if checkpoint_operation is not None:
      checkpoint['previous_checkpoint_id']=work['coding_checkpoints'][-1]['checkpoint_id']
      if checkpoint_operation['action']=='revise':checkpoint['root_checkpoint_id']=checkpoint_operation['root_checkpoint_id']
    checkpoint_control.finish(fresh,job,'completed',job['id'] if not chatting else None)
    save(fresh)
    if not chatting:start_checkpoint_teaching(fresh)
  except Exception as e:
   with task_lock(t['id']):
    fresh=load(t['id'])
    if fresh.get('coding_run',{}).get('id')==job['id']:
     detail=str(e) if isinstance(e,ValueError) else '执行器异常：'+type(e).__name__+'；本轮未完成'
     fresh['coding_run'].update(status='failed',detail=detail)
     checkpoint_control.finish(fresh,job,'failed',error=detail);save(fresh)
 threading.Thread(target=worker,daemon=True).start()

def checkpoint_command(t, checkpoint_id, action, body):
 operation,launch=checkpoint_control.prepare(t,checkpoint_id,action,body,read_project_files(t['id']))
 if not launch:return 200,{'operation':operation,'task':snapshot(t)}
 if operation['target_step']>=len(t['plan']):
  operation['status']='completed';operation['outcome']='development_finished';save(t)
  return 200,{'operation':operation,'task':snapshot(t)}
 # Configuration errors reject an uncommitted task copy, so acceptance is not lost.
 if not opencode_executor.metadata()['configured'] or not opencode_executor.binary():raise ValueError('请先连接并安装Coding执行器')
 instruction=operation['instruction'] or t['plan'][t['step']]
 if not t.get('messages') or t['messages'][-1].get('role')!='user' or t['messages'][-1].get('channel')!='coding' or t['messages'][-1].get('content')!=instruction:
  message(t,'coding','user',instruction)
 t['messages'][-1].update(source='student_confirmed_teaching_command',request_id=operation['request_id'])
 save(t)
 try:start_coding(t,instruction,checkpoint_operation=operation)
 except Exception as e:
  operation.update(status='failed',error=str(e) if isinstance(e,ValueError) else 'Coding启动失败')
  if t.get('coding_run',{}).get('checkpoint_operation',{}).get('request_id')==operation['request_id']:
   t['coding_run'].update(status='failed',detail='Coding启动失败；可使用相同请求重试')
  save(t)
 return 202,{'operation':operation,'task':snapshot(t)}

CODING=SampleCodingAgent(project,write_project_file)
PREVIEW_PORT=None

def safe_preview_name(name):
 import re
 return project_files.allowed(name) and Path(name).suffix.lower() in ('.html','.js','.mjs','.css','.svg','.json')

class PreviewHandler(BaseHTTPRequestHandler):
 def do_GET(self):
  parts=urlparse(self.path).path.strip('/').split('/')
  try:
   if len(parts)<3 or parts[0]!='preview' or not safe_preview_name('/'.join(parts[2:])): raise ValueError()
   uuid.UUID(parts[1]);p=project_files.target(DATA/parts[1]/'project','/'.join(parts[2:]))
   raw=p.read_bytes()
   if parts[2]=='index.html':
    script='''<script>
const report=(type,message,line)=>parent.postMessage({channel:'control-preview',task_id:TASK,type,message:String(message).slice(0,500),line:line||0},'*');
window.addEventListener('error',e=>report('error',e.message,e.lineno));
window.addEventListener('unhandledrejection',e=>report('error',e.reason,0));
window.addEventListener('load',()=>report('ready','页面已加载；这不代表所有功能通过验证',0));
</script>'''.replace('TASK',json.dumps(parts[1]))
    raw=raw.replace(b'<head>',b'<head>'+script.encode(),1)
   self.send_response(200);self.send_header('Content-Type',(mimetypes.guess_type(p.name)[0] or 'text/plain')+'; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
  except (ValueError,FileNotFoundError):self.send_error(404)
  except OSError:self.send_error(500,'Project file could not be read')

class Handler(BaseHTTPRequestHandler):
 def reply(self, code, obj, mime='application/json; charset=utf-8'):
  raw=json.dumps(obj,ensure_ascii=False).encode() if isinstance(obj,(dict,list)) else obj
  self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  try:
   parts=urlparse(self.path).path.strip('/').split('/')
   if parts==['api','health']: return self.reply(200,{'coding_mode':'sample_or_opencode','coding':opencode_executor.metadata(),'teaching':teaching.TeachingAgent().metadata(),'storage':'sqlite'})
   if parts==['api','tasks']:
    with connection() as c: rows=c.execute('SELECT body FROM tasks ORDER BY rowid DESC').fetchall()
    return self.reply(200,[{'id':(t:=json.loads(r[0]))['id'],'title':t['title']} for r in rows])
   if len(parts) in (4,5) and parts[:2]==['api','tasks'] and parts[3]=='checkpoints':
    with task_lock(parts[2]):
     task=load(parts[2]);events=task.get('coding_checkpoints',[])
     if len(parts)==5:return self.reply(200,checkpoint_control.find(task,parts[4]))
     return self.reply(200,{'session_id':task['id'],'items':events[-50:],'total':len(events)})
   if len(parts)==4 and parts[:2]==['api','tasks'] and parts[3]=='project-file':
    with task_lock(parts[2]):
     task=load(parts[2]);files=read_project_files(task['id']);query=parse_qs(urlparse(self.path).query)
     args={'path':query.get('path',[''])[0],'start_line':int(query.get('start_line',['1'])[0]),'limit':int(query.get('limit',['120'])[0])}
     result=teaching.dispatch_tool('read_project_file',args,{'files':{},'code_hash':knowledge.code_hash(files)},project_source=files)
     if query.get('checkpoint_id'):
      checkpoint=checkpoint_control.find(task,query['checkpoint_id'][0])
      result['stale_for_checkpoint']=checkpoint['project_evidence']['code_hash']!=result['code_hash']
     return self.reply(200,result)
   if len(parts)==4 and parts[:2]==['api','tasks'] and parts[3] in ('learning','learning-record.md'):
    with task_lock(parts[2]):
     task=load(parts[2]);teaching.state(task)
     if parts[3]=='learning':return self.reply(200,{'memory':memory.view(task),'learning':learning.view(task)})
     return self.reply(200,memory.report(task).encode('utf-8'),'text/markdown; charset=utf-8')
   if len(parts)==3 and parts[:2]==['api','tasks']:
    with task_lock(parts[2]): return self.reply(200,snapshot(load(parts[2])))
   if len(parts)==3 and parts[0]=='preview':
    uuid.UUID(parts[1]); p=project(parts[1])/parts[2]
    if not safe_preview_name(parts[2]): return self.reply(404,{'error':'文件不存在'})
    return self.reply(200,p.read_bytes(),mimetypes.guess_type(p.name)[0] or 'text/plain')
   name='index.html' if parts==[''] else '/'.join(parts)
   if name not in ['index.html','app.js','style.css']: return self.reply(404,{'error':'地址不存在'})
   p=ROOT/'frontend'/name
   return self.reply(200,p.read_bytes(),(mimetypes.guess_type(name)[0] or 'text/plain')+'; charset=utf-8')
  except UnicodeError: self.reply(422,{'error':'项目文件不是有效的 UTF-8 文本，请修复文件编码'})
  except (ValueError,FileNotFoundError): self.reply(404,{'error':'任务或文件不存在'})
  except (OSError,sqlite3.Error): self.reply(500,{'error':'读取文件或存储失败，请稍后重试'})
 def do_POST(self):
  host=self.headers.get('Host','');origin=self.headers.get('Origin')
  if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'): return self.reply(403,{'error':'仅允许本机访问'})
  if origin and origin!='http://'+host: return self.reply(403,{'error':'不允许跨站写入'})
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length<0:raise ValueError('请求长度不能为负数')
   if length>200000: return self.reply(413,{'error':'请求过大'})
   body=json.loads(self.rfile.read(length) or b'{}')
   if not isinstance(body,dict): raise ValueError('请求必须是对象')
   parts=urlparse(self.path).path.strip('/').split('/')
   with task_lock(parts[2] if len(parts)>3 and parts[:2]==['api','tasks'] else 'settings-or-create'):
    if parts==['api','settings','coding']:
     opencode_executor.configure(body.get('api_key'),body.get('model'),body.get('region'))
     return self.reply(200,opencode_executor.metadata())
    if parts==['api','settings','teaching']:
     provider=body.get('provider','deepseek')
     providers.configure(provider,body.get('api_key',''),body.get('model','deepseek-flash' if provider=='deepseek' else ''))
     return self.reply(200,{'configured':True,'provider':teaching.TeachingAgent().metadata()})
    if parts==['api','tasks']:
     tid=str(uuid.uuid4());t=dict(id=tid,title='待办事项 · 示例教程',mode='sample',stage='created',step=0,plan=[],plan_draft=[],messages=[],changes=[],checks=[])
     teaching.state(t)
     delivery=body.get('checkpoint_delivery','automatic')
     if delivery not in ('automatic','manual'):raise ValueError('checkpoint_delivery必须为automatic或manual')
     t['checkpoint_delivery']=delivery
     if body.get('coding_mode')=='opencode':
      t.update(mode='opencode',title='OpenCode · 分阶段开发（待连接模型）');coding_workflow.state(t)
     if t['mode']!='opencode':
      for name,content in FILES.items(): (project(tid)/name).write_text(content,encoding='utf-8')
     if t['mode']=='sample':message(t,'coding','assistant','你好，先说说你想开发什么。初版使用固定待办教程，示例 Agent 不调用真实模型。')
     message(t,'teaching','assistant','我会陪你检查计划和代码。先发送一句需求，再一起明确：什么样的输入应该被接受？')
     if t['mode']=='opencode':
      message(t,'coding','assistant','你好，有什么想开发的吗？我们可以先聊聊你的想法。')
     if body.get('scenario')=='teaching':
      t['title']='空白输入审查 · 教学预置示例';t['plan']=PLAN
      for step in range(2):
       CODING.step(t,'载入教学预置版本');t['step']+=1
      t['stage']='review'
      message(t,'coding','assistant','已载入可运行的教学预置版本。这里的遗漏来自固定教材示例，不是模型自然生成；请先审查代码和实际操作，不必继续执行第三步。')
      message(t,'teaching','assistant','这是教学预置的审查练习。你可以先预测提交不同输入的结果，再告诉我你的观察。')
    else:
     if len(parts)<4 or parts[:2]!=['api','tasks']: return self.reply(404,{'error':'接口不存在'})
     t=load(parts[2]); action='/'.join(parts[3:]); text=body.get('message','')
     if len(parts)==6 and parts[3]=='checkpoints':
      code,result=checkpoint_command(t,parts[4],parts[5],body);return self.reply(code,result)
     if t.get('coding_run',{}).get('status') in ('queued','running'):raise ValueError('Coding正在执行，请稍等')
     if t.get('teaching_run',{}).get('status') in ('queued','running'): raise ValueError('教师正在处理上一条消息，请稍等')
     if not isinstance(text,str) or len(text)>12000: raise ValueError('消息格式不正确或过长')
     observations=body.get('runtime_observations')
     if isinstance(observations,list):
      t['runtime_observations']=[{'type':x.get('type'),'message':x.get('message','')[:500],'line':x.get('line',0),'source':'browser_report_not_verified_test'} for x in observations[-20:] if isinstance(x,dict) and x.get('type') in ('ready','error') and isinstance(x.get('message'),str)]
     if action=='coding/generate-plan':
      if t.get('mode')!='opencode' or t['plan']:raise ValueError('当前不能生成计划')
      if not text.strip():raise ValueError('请输入需求')
      message(t,'coding','user',text);start_coding(t,text,True);return self.reply(202,snapshot(t))
     elif action=='coding/plan-draft':
      if t.get('mode')!='opencode':raise ValueError('仅OpenCode工作流支持此入口')
      coding_workflow.set_plan(t,body.get('plan'));message(t,'coding','user','阶段计划草稿：\n'+'\n'.join(t['plan_draft']))
     elif action=='coding/capabilities':
      if t.get('mode')!='opencode':raise ValueError('仅OpenCode工作流支持此入口')
      enabled=body.get('experience_enabled')
      if type(enabled) is not bool:raise ValueError('经验开关必须是布尔值')
      coding_workflow.state(t)['experience_enabled']=enabled
      coding_workflow.event(t,'experience_toggle','经验加载'+('启用' if enabled else '停用'))
     elif action=='coding/preflight':
      if t.get('mode')!='opencode' or not t['plan'] or t['step']>=len(t['plan']):raise ValueError('请先确认阶段计划')
      packet=coding_workflow.prepare(t,t['plan'][t['step']],learning.coding_packet(t,t['plan'][t['step']]))
      coding_workflow.inspect_phase(t,packet)
     elif action=='plan':
      if t['plan']: raise ValueError('已有计划，请在聊天中补充要求')
      if not text.strip(): raise ValueError('先输入需求')
      if t.get('mode')=='opencode':raise ValueError('模型尚未连接，请在阶段草稿入口设置计划；不会生成固定示例计划')
      message(t,'coding','user',text);t['plan_draft']=PLAN.copy();t['stage']='planning'
      message(t,'coding','assistant','这是固定教程的计划草稿，尚未开始开发：\n\n'+ '\n'.join(f'{i+1}. {p}' for i,p in enumerate(t['plan_draft']))+'\n\n请与教师讨论目标和拆分方式，编辑并确认后才会成为开发计划。')
     elif action=='plan/confirm':
      steps=body.get('plan')
      if t['plan'] or not t.get('plan_draft'): raise ValueError('当前没有可确认的计划草稿')
      if not body.get('confirmed') or not isinstance(steps,list) or not 1<=len(steps)<=12 or any(not isinstance(x,str) or not x.strip() or len(x)>300 for x in steps): raise ValueError('请明确确认有效的分步计划')
      t['plan']=[x.strip() for x in steps];t['stage']='review'
      if t.get('mode')=='opencode':coding_workflow.confirm(t)
      message(t,'coding','user','我确认开发计划：\n'+'\n'.join(t['plan']))
      message(t,'coding','assistant','阶段计划已确认，每阶段结束后暂停；模型/API尚未连接，当前不执行代码。' if t.get('mode')=='opencode' else '开发计划已确认；当前仍未执行代码。示例执行器按固定待办教材演示，真实模型尚未接入。')
     elif action in ['coding/messages','teaching/messages']:
      if not text.strip(): raise ValueError('消息不能为空')
      ch=action.split('/')[0];message(t,ch,'user',text)
      if ch=='coding' and t.get('mode')=='opencode':
       command=text.strip().rstrip('。！!')
       if command in ('确认计划','就按这个计划','按这个计划做'):
        if t['plan'] or not t.get('plan_draft'):raise ValueError('请先形成待确认的计划')
        t['plan']=list(t['plan_draft']);coding_workflow.confirm(t)
        message(t,'coding','assistant','计划已锁定。可以先讨论，也可以告诉我开始当前阶段。');save(t);return self.reply(200,snapshot(t))
       if command in ('检查通过','本步通过','当前阶段通过'):
        coding_workflow.accept_phase(t);message(t,'coding','assistant','已记录检查通过，当前已暂停。');save(t);return self.reply(200,snapshot(t))
       if command=='返工当前阶段':
        if not t['plan'] or t['step']>=len(t['plan']):raise ValueError('没有当前阶段')
        start_coding(t,t['plan'][t['step']]+'；根据最近学生反馈返工，仅此阶段');return self.reply(202,snapshot(t))
       if command in ('开始','开始开发','执行当前阶段','继续','继续下一阶段'):
        if not t['plan'] or t['step']>=len(t['plan']):raise ValueError('请先确认计划，或所有阶段已通过')
        checkpoints=coding_workflow.state(t)['checkpoints']
        if checkpoints[t['step']]['status']=='executed_pending_review':raise ValueError('当前阶段待检查，请先反馈问题或确认检查通过')
        start_coding(t,t['plan'][t['step']]);return self.reply(202,snapshot(t))
       import re
       wants_edit=coding_workflow.message_intent(command)=='execute'
       if wants_edit and not t.get('plan') and coding_workflow.direct_file_request(command):
        t['plan']=[text[:300]];t['plan_draft']=list(t['plan']);coding_workflow.confirm(t)
        coding_workflow.state(t)['plan_source']='student_direct_file_instruction'
       if wants_edit and t.get('plan'):
        if t['step']>=len(t['plan']):raise ValueError('已确认计划全部完成，如需新任务请先制定新计划')
        if coding_workflow.state(t)['checkpoints'][t['step']]['status']=='executed_pending_review' and t.get('coding_checkpoints'):
         checkpoint=t['coding_checkpoints'][-1]
         code,result=checkpoint_command(t,checkpoint['checkpoint_id'],'revise',{'session_id':t['id'],'request_id':str(uuid.uuid4()),'confirmed':True,'instruction':text,'expected_code_hash':knowledge.code_hash(read_project_files(t['id']))})
         return self.reply(code,result['task'])
        start_coding(t,t['plan'][t['step']]+'\n学生补充：'+text);return self.reply(202,snapshot(t))
       if wants_edit and not t.get('plan'):
        save(t);raise ValueError('已识别为执行请求，请先确认项目开发计划；也可直接要求创建具体代码文件')
       start_coding(t,text,chatting=True);return self.reply(202,snapshot(t))
      if ch=='teaching':
       start_teaching(t);return self.reply(202,snapshot(t))
      else: message(t,ch,'assistant','补充要求已保存，Teaching可读取；模型/API未配置，当前不会自动改代码。' if t.get('mode')=='opencode' else '补充要求已保存，Teaching Agent 也可以读取。点击执行前可在确认框中编辑本步指令；示例适配器仍按固定教程修改文件。')
     elif action in ('teaching/review','evaluate'):
      start_teaching(t,'review' if action=='teaching/review' else 'evaluate');return self.reply(202,snapshot(t))
     elif action=='teaching/knowledge':
      topic=body.get('topic');choice=body.get('choice')
      if topic not in teaching.KNOWLEDGE or choice not in ('learn','later'): raise ValueError('请选择有效的技术主题与学习方式')
      course=teaching.state(t)['course'];course['knowledge_preferences'][topic]=choice
      course['selected_knowledge']=topic if choice=='learn' else None
      message(t,'teaching','user',('我想了解：' if choice=='learn' else '先跳过技术扩展：')+teaching.KNOWLEDGE[topic]['title'])
      if choice=='learn':
       start_teaching(t,'knowledge');return self.reply(202,snapshot(t))
      t['messages'].append({'channel':'teaching','role':'system','content':'已记下稍后再学。继续当前项目；跳过扩展不影响开发或评价。'})
     elif action=='teaching/transfer':
      s=teaching.state(t)
      if not s.get('pending_transfer'): raise ValueError('教师尚未提出迁移题')
      if not text.strip(): raise ValueError('请提交迁移题作答')
      s['transfer_answer']={'question':s['pending_transfer']['question'],'answer':text,'message_id':len(t['messages'])}
      message(t,'teaching','user',text);start_teaching(t,'evaluate');return self.reply(202,snapshot(t))
     elif action=='upgrade-proposals':
      s=teaching.state(t)
      if not body.get('confirmed'): raise ValueError('需要学生确认整理改进建议')
      if s['assessment']!='candidate' or not s['transfer_answer']: raise ValueError('掌握证据不足，暂不能形成升级申请')
      if not s['turns'] or not s['turns'][-1]['result']['upgrade_suggestion']: raise ValueError('教师尚未形成改进建议')
      if teaching.context(snapshot(t),'evaluate')['code_hash']!=s['turns'][-1]['code_hash']: raise ValueError('代码已变化，请重新评价')
      proposal={'id':str(uuid.uuid4()),'status':'pending_review','method':None,
       'source_task':t['id'],'source_turn':s['turns'][-1]['id'],
       'suggestion':s['turns'][-1]['result']['upgrade_suggestion'],
       'code_hash':s['turns'][-1]['code_hash'],'applied':False}
      s['upgrade_requests'].append(proposal)
     elif action=='knowledge/manual':
      knowledge.add_manual(t,body.get('title'),body.get('content'),knowledge.code_hash(read_project_files(t['id'])),body.get('confirmed'))
     elif action=='knowledge/settings':
      if type(body.get('enabled')) is not bool:raise ValueError('enabled必须为布尔值')
      t['knowledge_enabled']=body['enabled']
     elif action=='knowledge/search':
      with connection() as c:items=knowledge.search(c,t['id'],body.get('query',''),knowledge.code_hash(read_project_files(t['id'])),body.get('limit',3))
      return self.reply(200,{'items':items})
     elif action.startswith('knowledge/'):
      pieces=action.split('/')
      if len(pieces)!=3 or pieces[2]!='review' or body.get('confirmed') is not True:raise ValueError('请确认有效的知识审核操作')
      knowledge.review(t,pieces[1],body.get('decision'),body.get('reviewer'),body.get('note',''))
     elif action.startswith('experiences/'):
      pieces=action.split('/')
      if len(pieces)!=3:raise ValueError('经验操作路径无效')
      learning.set_experience(t,pieces[1],pieces[2],body.get('confirmed'))
     elif action.startswith('skill-unlocks/'):
      pieces=action.split('/')
      if len(pieces)!=2:raise ValueError('Skill申请路径无效')
      learning.request_unlock(t,pieces[1],body.get('confirmed'))
     elif action=='steps/run':
      if t.get('mode')=='opencode':
       if body.get('confirmed') is not True or type(body.get('expected_step')) is not int or body['expected_step']!=t['step'] or not t['plan'] or t['step']>=len(t['plan']):raise ValueError('请确认有效的当前阶段')
       if coding_workflow.state(t)['checkpoints'][t['step']]['status']=='executed_pending_review':raise ValueError('当前阶段待学生检查')
       instruction=body.get('instruction','')
       if not isinstance(instruction,str) or not instruction.strip() or len(instruction)>12000:raise ValueError('请填写本步指令')
       message(t,'coding','user','确认执行：'+instruction);start_coding(t,instruction);return self.reply(202,snapshot(t))
      if not body.get('confirmed'): raise ValueError('需要学生明确确认')
      if not t['plan'] or t['step']>=len(t['plan']): raise ValueError('当前没有可执行步骤')
      if type(body.get('expected_step')) is not int: raise ValueError('expected_step 必须是整数')
      if body.get('expected_step')!=t['step']: raise ValueError('步骤已变化，请刷新后确认')
      instruction=body.get('instruction','')
      if not isinstance(instruction,str) or not instruction.strip() or len(instruction)>12000: raise ValueError('请填写确认指令')
      message(t,'coding','user','确认执行：'+instruction)
      packet=learning.coding_packet(t,instruction)
      ls=learning.state(t);ls['coding_loads'].append({'step':t['step'],'rule_versions':[{'id':r['id'],'revision':r['revision']} for r in packet['rules']], 'applied':False,'adapter':'sample_records_only'});ls['revision']+=1
      before=read_project_files(t['id']);stage_index=t['step']
      answer=CODING.step(t,instruction,packet);t['step']+=1;t['stage']='review';message(t,'coding','assistant',answer)
      checkpoint_events.record(t,str(uuid.uuid4()),instruction,answer,before,read_project_files(t['id']),stage_index)
     elif action=='files':
      name=body.get('path');content=body.get('content')
      if name not in read_project_files(t['id']) or not isinstance(content,str): raise ValueError('文件或内容不正确')
      p=project(t['id'])/name;before=p.read_text(encoding='utf-8');write_project_file(p,content);t['changes'].append(dict(file=name,before=before,after=content,instruction='学生手动保存'))
      s=teaching.state(t);s['assessment']='insufficient';s['transfer_answer']=None;s['pending_transfer']=None
     elif action=='verify':
      code=(project(t['id'])/'app.js').read_text(encoding='utf-8')
      checks=[{'name':'空白输入检查标记','pass':'trim()' in code and 'if (!title)' in code},{'name':'本地保存调用标记','pass':'localStorage.setItem' in code}]
      t['checks']=checks;message(t,'coding','assistant','静态演示检查：'+ '；'.join(x['name']+('存在' if x['pass'] else '缺失') for x in checks)+'。这不是行为测试，请打开预览实际验证。')
     else: return self.reply(404,{'error':'接口尚未实现'})
    if parts!=['api','tasks'] and action in ('plan','steps/run'):
     teaching.state(t)['assessment']='insufficient'
     teaching.state(t)['transfer_answer']=None
     teaching.state(t)['pending_transfer']=None
     if action=='steps/run':
      save(t);start_checkpoint_teaching(t)
     else:start_teaching(t,'review')
     return self.reply(202,snapshot(t))
    save(t);self.reply(200,snapshot(t))
  except UnicodeError: self.reply(422,{'error':'文件或请求不是有效的 UTF-8 文本，请检查编码'})
  except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e: self.reply(400,{'error':str(e)})
  except (OSError,sqlite3.Error): self.reply(500,{'error':'文件或记录保存失败，请检查本地文件与存储后重试'})

class LocalHTTPServer(ThreadingHTTPServer):
 # On Windows SO_REUSEADDR can let old/new backends share a port.
 allow_reuse_address=False
 def server_bind(self):
  if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
   self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
  super().server_bind()

def create_preview_server(preferred_port):
 for port in [preferred_port,0]:
  try:return LocalHTTPServer(('127.0.0.1',port),PreviewHandler)
  except OSError:
   if port==0:raise

def recover_interrupted(t):
 changed=False
 for key in ('coding_run','teaching_run'):
  if t.get(key,{}).get('status') in ('queued','running'):
   t[key].update(status='failed',detail='服务重启中断了上次执行，请检查项目后重试')
   if key=='coding_run':checkpoint_control.finish(t,t[key],'failed',error='service_restarted')
   if key=='teaching_run':
    for checkpoint in t.get('coding_checkpoints',[]):
     if checkpoint['checkpoint_id']==t[key].get('checkpoint_id'):
      checkpoint['delivery'].update(status='failed',error='service_restarted')
   changed=True
 return changed

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8772);args=parser.parse_args()
 print(f'Control workbench: http://127.0.0.1:{args.port} · SAMPLE AGENTS',flush=True)
 with connection() as c:
  for (body,) in c.execute('SELECT body FROM tasks').fetchall():
   t=json.loads(body)
   if recover_interrupted(t):
    c.execute('UPDATE tasks SET body=? WHERE id=?',(json.dumps(t,ensure_ascii=False),t['id']))
 try:server=LocalHTTPServer(('127.0.0.1',args.port),Handler)
 except OSError:raise SystemExit('工作台端口已被占用，请先关闭旧后台，或使用 --port 选择其他端口。') from None
 try:preview_server=create_preview_server(args.port+1)
 except OSError as err:
  server.server_close();raise SystemExit('无法启动项目预览，请检查本机可用端口。') from None
 PREVIEW_PORT=preview_server.server_port
 threading.Thread(target=preview_server.serve_forever,daemon=True).start()
 print(f'Project preview: http://127.0.0.1:{PREVIEW_PORT}',flush=True)
 server.serve_forever()
