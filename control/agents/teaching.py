"""Teaching context, pacing and provider adapter. No coding tools or upgrade execution."""
import hashlib
import json
import os
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PHASES = ['observe', 'explain', 'propose', 'verify', 'transfer']
LESSON = {
 'id': 'input-validation',
 'goal': '学生能识别空白输入，解释输入检查应放在哪里，并设计正常和边界验证。',
 'sources': [
  {'id':'mdn-trim','url':'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/trim',
   'fact':'trim() 返回去掉两端空白的新字符串，不修改原字符串。'},
  {'id':'mdn-storage','url':'https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage',
   'fact':'localStorage 的数据通常可跨浏览器会话保留，按来源隔离。'},
  {'id':'mdn-dom','url':'https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model',
   'fact':'DOM把网页文档表示为对象和节点树，脚本可访问并改变结构、样式和内容。'},
  {'id':'mdn-events','url':'https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/addEventListener',
   'fact':'addEventListener为目标注册事件监听函数，在对应事件发生时调用。'}],
 'transfer_question':'如果昵称输入框只输入空格就提交，你会怎样判断和处理？写出一个正常输入、一个边界输入的预期结果；不要照抄当前待办代码。',
 'rubric': ['指出具体操作和现象','解释输入流与代码依据','提出检查位置和条件','提供正常和边界验证','迁移到昵称的新情境']
}
ASSETS = Path(__file__).resolve().parent / 'teaching_assets'
SYSTEM = (ASSETS / 'system.md').read_text(encoding='utf-8')
ACTIONS = ['ask', 'hint', 'explain', 'summarize', 'ask_transfer', 'assess', 'pause']
SKILLS = ['diagnose', 'socratic-review', 'explain', 'assess-summarize', 'upgrade-proposal']
KNOWLEDGE = {
 'page-structure':{'title':'HTML、CSS、JavaScript 怎样分工','when':'理解整体项目与页面代码','source_ids':['mdn-dom']},
 'events':{'title':'点击和提交怎样触发代码','when':'解释表单提交、添加与完成操作','source_ids':['mdn-events','mdn-dom']},
 'input':{'title':'输入值、字符串和空白检查','when':'理解当前代码后审查输入处理','source_ids':['mdn-trim']},
 'storage':{'title':'页面状态与本地保存','when':'讨论刷新后的数据变化','source_ids':['mdn-storage']}}
COURSE_OBJECTIVES = [
 {'id':'requirements','title':'明确需求与验收条件'},
 {'id':'input-validation','title':'审查输入处理并解释原因'},
 {'id':'verification','title':'设计验证并检查数据保留'}]

# Immutable strategy definition for the second-version teaching pilot.
STRATEGIES = [{
 'id':'todo-input-v1','family_id':'todo-input-validation','version':1,
 'name':'待办输入边界：先观察再分级提示','status':'active',
 'scope':'todo-empty-input-validation',
 'content':{
  'steps':[
   '先让学生预测并观察正常输入、空输入和纯空格输入，不先指出缺陷位置。',
   '追问观察到的现象及输入值从表单进入列表的代码依据。',
   '只在学生卡住时逐级提示：比较输入 → 查看提交处理 → 解释空白规范化和空值判断。',
   '让学生用自己的话提出修复要求和验证办法；执行修改前必须由学生确认。',
   '检查正常输入仍可添加、空输入和纯空格被拒绝；源码标记不能代替行为观察。',
   '最后提供不同表面情境的独立迁移题，不先给提示或答案。'],
  'hint_levels':[
   '只追问现象和判断依据。',
   '提示比较正常值、空值和纯空格值。',
   '提示查看表单提交处理中的输入读取和条件判断。',
   '解释首尾空白处理和空值检查，但不提供当前练习的完整修复代码。'],
  'out_of_scope':['数据持久化','完成状态','视觉样式','代码风格'],
  'transfer_question':LESSON['transfer_question']
 }}]

def strategy(strategy_id):
 return next((item for item in STRATEGIES if item['id']==strategy_id),None)

def state(t):
 s=t.setdefault('teaching', {'phase':'observe','hint_level':0,'assessment':'insufficient',
  'turns':[], 'transfer_answer':None,'upgrade_requests':[],'plan':{},'pending_transfer':None})
 s.setdefault('plan',{});s.setdefault('pending_transfer',None)
 s.setdefault('course',{'title':'待办项目：从需求到验证','overall_goal':'能够组织AI开发，并独立审查和验证结果',
  'objectives':[{**g,'evidence_ids':[],'observations':[]} for g in COURSE_OBJECTIVES],
  'summary':'尚未形成接续摘要，先读取已有原始对话。','summary_kind':'model_notes_not_verified_facts',
  'resume_note':'从当前项目和学生已有判断接着教，不重新开课。','checkpoints':[]})
 s['course'].setdefault('knowledge_preferences',{})
 s['course'].setdefault('selected_knowledge',None)
 return s

def context(t, action):
 s=state(t)
 active_strategy=strategy(t.get('strategy_version_id'))
 files=t.get('files',{})
 code_hash=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
 # One bounded tutorial project, never arbitrary workspace files.
 loaded=['diagnose','socratic-review','explain']
 if action=='evaluate' or s['phase']=='transfer': loaded.append('assess-summarize')
 students=[{'id':i,'content':m['content'],'channel':m['channel']} for i,m in enumerate(t['messages']) if m['role']=='user']
 remembered={i for g in s['course']['objectives'] for i in g['evidence_ids'][-5:]}
 selected={m['id']:m for m in students[-80:]}
 selected.update({m['id']:m for m in students if m['id'] in remembered})
 course_view={**s['course'],'checkpoints':s['course']['checkpoints'][-8:],
  'objectives':[{**g,'observations':g['observations'][-5:],'evidence_ids':g['evidence_ids'][-10:]} for g in s['course']['objectives']]}
 return {'action':action,'lesson':LESSON,'strategy':active_strategy,'phase':s['phase'],'hint_level':s['hint_level'],
  'plan':t['plan'],'plan_draft':t.get('plan_draft',[]),'plan_confirmed':bool(t['plan']),'step':t['step'],
  'project_purpose':'待办网页：用户添加事项、标记完成，并讨论输入限制和数据保留。',
  'knowledge_map':KNOWLEDGE,
  'files':{k:[{'line':i+1,'text':line} for i,line in enumerate(v.splitlines())] for k,v in files.items()},
  'code_hash':code_hash,'changes':t['changes'][-2:], 'checks':t['checks'],
  'check_type':'source_markers_only_not_behavioral',
  'runtime_observations':t.get('runtime_observations',[]),
  'messages':[{'id':i,**m} for i,m in enumerate(t['messages'])][-50:],
  'student_evidence':list(selected.values()),
  'loaded_skills':{name:dispatch_tool('read_teaching_skill',{'name':name},{})['content'] for name in loaded},
  'transfer_question':LESSON['transfer_question'] if s['phase']=='transfer' else None,
  'transfer_answer':s['transfer_answer'],'pending_transfer':s.get('pending_transfer'),
  'teaching_plan':s.get('plan',{}),'recent_teaching':s['turns'][-6:],
  'course':course_view,'project_change':{'code_changed':s['course'].get('last_code_hash')!=code_hash,'current_step':t['step']},
  'skills_available':SKILLS}

def validate(output, ctx):
 if not isinstance(output,dict): raise ValueError('教师输出不是对象')
 if not isinstance(output.get('reply'),str) or not output['reply'].strip() or len(output['reply'])>4000: raise ValueError('教师回复格式错误')
 phase=output.get('next_phase')
 if phase not in PHASES: raise ValueError('关注点不在允许范围')
 if output.get('teaching_action') not in ACTIONS: raise ValueError('教学动作不合法')
 plan=output.get('plan')
 if not isinstance(plan,dict) or any(not isinstance(plan.get(k),str) or not plan[k].strip() for k in ('goal','reason','next_step')): raise ValueError('缺少教学目标、理由或下一步安排')
 if not isinstance(plan.get('open_questions'),list) or any(not isinstance(q,str) for q in plan['open_questions']): raise ValueError('待解决问题格式错误')
 if not isinstance(output.get('transfer_question',''),str): raise ValueError('迁移题格式错误')
 if output['teaching_action']=='ask_transfer' and not output.get('transfer_question','').strip(): raise ValueError('未提供迁移题')
 if type(output.get('hint_level')) is not int or not 0<=output['hint_level']<=3: raise ValueError('提示级别错误')
 if output.get('assessment') not in ('insufficient','developing','candidate'): raise ValueError('评价格式错误')
 if output.get('issue_kind') not in ('hypothesis','confirmed','none'): raise ValueError('问题证据类型错误')
 for key in ('citations','source_ids','student_evidence_ids'):
  if not isinstance(output.get(key),list): raise ValueError('证据列表缺失')
 for cite in output['citations']:
  if not isinstance(cite,dict): raise ValueError('引用格式错误')
  if not isinstance(cite.get('file'),str) or not isinstance(cite.get('quote'),str): raise ValueError('源码引用格式错误')
  lines=ctx['files'].get(cite.get('file'),[]); n=cite.get('line')
  if type(n) is not int or n<1 or n>len(lines): raise ValueError('源码行号与当前文件不一致')
  quote=cite['quote'].strip();original=lines[n-1]['text'].strip()
  if quote!=original or not re.search(r'[\w$]',quote): raise ValueError('源码引用需为完整有效代码行，不能只引单字或标点')
 if output['issue_kind']=='confirmed' and not output['citations']: raise ValueError('已确认的代码问题需要源码依据')
 allowed={s['id'] for s in LESSON['sources']}
 if any(not isinstance(i,str) or i not in allowed for i in output['source_ids']): raise ValueError('教师引用了未提供的材料')
 students={m['id'] for m in ctx.get('student_evidence',ctx['messages']) if m.get('role','user')=='user'}
 # Numeric JSON strings are normalized only when they point to real evidence.
 output['student_evidence_ids']=[int(i) if isinstance(i,str) and i.isascii() and i.isdigit() else i for i in output['student_evidence_ids']]
 if any(type(i) is not int or i not in students for i in output['student_evidence_ids']):
  output['validation_warnings']=['学生引用编号无效：本轮保留教学回复，不采纳掌握或升级建议。']
  output['student_evidence_ids']=[];output['assessment']='insufficient';output['upgrade_suggestion']=''
 if output['assessment']!='insufficient' and not output['student_evidence_ids']: raise ValueError('评价需要学生证据')
 if output['assessment']=='candidate' and not ctx['transfer_answer']: raise ValueError('没有迁移作答不能建议掌握')
 if output['assessment']=='candidate' and ctx['transfer_answer']['message_id'] not in output['student_evidence_ids']: raise ValueError('候选掌握必须引用迁移作答')
 if not isinstance(output.get('upgrade_suggestion'),str): raise ValueError('改进建议格式错误')
 update=output.get('course_update')
 if update is not None:
  if not isinstance(update,dict) or any(not isinstance(update.get(k),str) or not update[k].strip() or len(update[k])>1500 for k in ('summary','resume_note')): raise ValueError('教程接续记录格式错误')
  ids=update.get('addressed_objective_ids',[])
  if not isinstance(ids,list) or any(not isinstance(i,str) or i not in [g['id'] for g in COURSE_OBJECTIVES] for i in ids): raise ValueError('教程目标不存在')
 diagram=output.get('mindmap')
 if diagram is not None:
  if not isinstance(diagram,dict) or not isinstance(diagram.get('title'),str) or not 1<=len(diagram['title'])<=30: raise ValueError('思维导图标题不合法')
  branches=diagram.get('branches')
  if not isinstance(branches,list) or not 1<=len(branches)<=4: raise ValueError('思维导图须有1到4个主分支')
  for branch in branches:
   if not isinstance(branch,dict) or not isinstance(branch.get('label'),str) or not 1<=len(branch['label'])<=24 or not isinstance(branch.get('children'),list) or len(branch['children'])>4: raise ValueError('思维导图分支不合法')
   if any(not isinstance(c,dict) or not isinstance(c.get('label'),str) or not 1<=len(c['label'])<=40 for c in branch['children']): raise ValueError('思维导图节点不合法')
 return output

class TeachingAgent:
 @property
 def mode(self): return os.getenv('TEACHING_MODE', 'model' if os.getenv('DEEPSEEK_API_KEY') else 'sample')
 def metadata(self):
  if self.mode!='model': return {'mode':'sample','model':'scripted-demo'}
  endpoint=os.getenv('TEACHING_ENDPOINT','https://api.deepseek.com/chat/completions')
  return {'mode':'model','model':os.getenv('TEACHING_MODEL','deepseek-flash'),'endpoint':endpoint}
 def respond(self, ctx, progress=None):
  progress=progress or (lambda *a:None)
  if self.mode=='sample':
   questions={
    'observe':'请先预测：输入只有空格的待办并提交，会发生什么？再打开预览操作一次，说出预期和实际的区别。',
    'explain':'请沿着输入值进入列表的路径读代码：哪一行决定能不能添加？它为什么会接受空格？',
    'propose':'你准备在什么位置增加什么条件？先用自己的话描述，让 Coding Agent 能照着执行。',
    'verify':'请写出一个正常输入和一个边界输入的预期结果，再实际操作。当前静态检查不能代替运行验证。',
    'transfer':LESSON['transfer_question']}
   question=questions[ctx['phase']]
   if not ctx['plan_confirmed']:
    question='先梳理项目目标和计划。这份待办示例中，用户要做哪些事？你认为第一版必须完成哪一项，什么可以以后再做？' if ctx['plan_draft'] else '我们先设置计划：你希望待办网页帮你做什么？先在 Coding 聊天里说出一个最小目标，我会帮你审查它的拆分。'
   if ctx['action']=='knowledge':question='这是示例模式；真实教师连接后会根据你选择的技术主题补讲。跳过扩展不影响继续开发。'
   return {'reply':'【示例教学，未调用模型】\n'+question, 'next_phase':ctx['phase'],
    'hint_level':ctx['hint_level'],'assessment':'insufficient','student_evidence_ids':[],
    'citations':[],'source_ids':[],'issue_kind':'none','upgrade_suggestion':'',
    'teaching_action':'ask','plan':{'goal':LESSON['goal'],'reason':'离线演示，不推断学生掌握程度','next_step':'请学生观察实际行为','open_questions':[]},'transfer_question':''}
  endpoint=os.getenv('TEACHING_ENDPOINT','https://api.deepseek.com/chat/completions')
  model=os.getenv('TEACHING_MODEL','deepseek-flash')
  key=os.getenv('TEACHING_API_KEY') or os.getenv('DEEPSEEK_API_KEY','')
  u=urlparse(endpoint)
  if not model or not u.hostname or (u.scheme!='https' and not(u.scheme=='http' and u.hostname in ('127.0.0.1','localhost'))):
   raise ValueError('模型地址或名称未正确配置')
  if u.hostname=='api.deepseek.com' and not key: raise ValueError('未配置 DEEPSEEK_API_KEY；请使用本机 DeepSeek 启动入口')
  messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(ctx,ensure_ascii=False)}]
  self.tool_trace=[]
  repaired=False
  budget={'attempts':0,'deadline':time.monotonic()+120}
  for iteration in range(5):
   if budget['attempts']>=5: raise ValueError('本轮请求预算已用完，可稍后重试')
   progress('thinking','正在结合代码和你的回答组织教学回复')
   payload={'model':model,'messages':messages,'max_tokens':2600}
   if budget['attempts']<4: payload['tools']=tools()
   if u.hostname=='api.deepseek.com':
    payload['thinking']={'type':'disabled'}
    if budget['attempts']==4: payload['response_format']={'type':'json_object'}
   req=Request(endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+key} if key else {})})
   try:
    raw=request_model(req,budget,progress)
    msg=raw['choices'][0]['message']; calls=msg.get('tool_calls',[])
    if calls:
     if budget['attempts']>=5 or len(calls)>5: raise ValueError('教学工具调用超出本轮预算')
     messages.append(msg)
     for call in calls:
      name=call['function']['name']
      try:
       args=json.loads(call['function']['arguments']); result=dispatch_tool(name,args,ctx)
      except (ValueError,TypeError,KeyError) as e:
       result={'error':str(e)}; args={}
      progress('reading','正在读取教学方法或项目证据')
      self.tool_trace.append({'name':name,'arguments':args,'success':'error' not in result})
      messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
     continue
    text=msg.get('content') or ''
    if text.startswith('```'): text=text.split('\n',1)[1].rsplit('```',1)[0]
    if not text.strip(): raise ValueError('教师返回空内容，请重试')
    try:
     output=validate(json.loads(text),ctx)
    except ValueError as err:
     if repaired or iteration==4: raise
     repaired=True;progress('validating','正在校对回复中的源码与证据引用')
     messages.extend([{'role':'assistant','content':text},{'role':'user','content':'上次JSON未通过校验：'+str(err)+'。请修正字段后返回JSON；student_evidence_ids只能从student_evidence的id原样选取。'}])
     continue
    return output
   except HTTPError as err:
    reason='请检查密钥与账户权限' if err.code in (401,403) else '服务繁忙，请稍后重试' if err.code==429 or err.code>=500 else '请检查模型与接口配置'
    raise ValueError(f'模型服务返回 HTTP {err.code}，{reason}。原始作答已保存。') from None
   except (URLError,TimeoutError,OSError,KeyError,IndexError,TypeError,json.JSONDecodeError):
    raise ValueError('Teaching 请求失败或响应格式错误；请检查服务配置后重试，原始作答已保存。') from None
  raise ValueError('本轮工具预算耗尽，未形成教学回复')

def request_model(req,budget,progress):
 retries=0
 while budget['attempts']<5:
  remaining=budget['deadline']-time.monotonic()
  if remaining<=0: raise ValueError('本轮等待超过120秒，请稍后重试')
  budget['attempts']+=1
  try:
   with urlopen(req,timeout=min(30,remaining)) as response:return json.load(response)
  except HTTPError as err:
   if not (err.code==429 or 500<=err.code<600) or retries>=2 or budget['attempts']>=5: raise
   delay=2**retries
   value=err.headers.get('Retry-After') if err.headers else None
   if value:
    try: delay=max(delay,float(value))
    except ValueError:
     try: delay=max(delay,parsedate_to_datetime(value).timestamp()-time.time())
     except (ValueError,TypeError,OverflowError): pass
   delay=min(8,delay)
   if time.monotonic()+delay>=budget['deadline']: raise ValueError('服务繁忙且本轮等待时间已用完，请稍后重试') from None
   retries+=1;progress('retrying',f'模型服务暂时繁忙，{delay:g}秒后自动重试（{retries}/2）')
   time.sleep(delay)
 raise ValueError('本轮请求预算已用完')

def tools():
 definitions=[('read_teaching_skill','按需读取额外教学方法，已预载的方法不必重复读取','name',SKILLS),
  ('read_project_file','查看当前任务已保存源码的真实行号','path',['app.js','index.html','style.css']),
  ('read_reference','读取已核实知识原理及来源','id',[r['id'] for r in LESSON['sources']]),
  ('read_learning_record','查看整门教程和已有教学记录','section',['course','plan','turns','messages','checks'])]
 return [{'type':'function','function':{'name':name,'description':desc,'parameters':{
  'type':'object','properties':{arg:{'type':'string','enum':options}},'required':[arg],'additionalProperties':False}}}
  for name,desc,arg,options in definitions]

def dispatch_tool(name,args,ctx):
 if not isinstance(args,dict): raise ValueError('工具参数必须为对象')
 if name=='read_teaching_skill':
  selected=args.get('name')
  if selected not in SKILLS: raise ValueError('未知教学Skill')
  return {'name':selected,'content':(ASSETS/'skills'/selected/'SKILL.md').read_text(encoding='utf-8')}
 if name=='read_project_file':
  path=args.get('path')
  if not isinstance(path,str) or path not in ctx['files']: raise ValueError('只能读取当前任务的指定文件')
  return {'path':path,'lines':ctx['files'][path],'code_hash':ctx['code_hash']}
 if name=='read_reference':
  for ref in LESSON['sources']:
   if ref['id']==args.get('id'): return ref
  raise ValueError('不存在该资料')
 if name=='read_learning_record':
  section=args.get('section'); mapping={'course':'course','plan':'teaching_plan','turns':'recent_teaching','messages':'messages','checks':'checks'}
  if section not in mapping: raise ValueError('未知记录类别')
  return {'section':section,'content':ctx[mapping[section]]}
 raise ValueError('不允许该工具')

def run(t, action='message', progress=None):
 s=state(t);ctx=context(t,action);agent=TeachingAgent()
 turn_id=s.get('next_turn_id',max((r['id'] for r in s['turns']),default=-1)+1)
 output=validate(agent.respond(ctx,progress),ctx)
 s['phase']=output['next_phase'];s['hint_level']=max(s['hint_level'],output['hint_level'])
 s['assessment']=output['assessment'];s['plan']=output['plan']
 if output.get('mindmap'):
  s['mindmap']=output['mindmap'];s['mindmap_code_hash']=ctx['code_hash']
 course=s['course'];update=output.get('course_update',{})
 if update:
  course['summary']=update['summary'];course['resume_note']=update['resume_note']
  for goal in course['objectives']:
   if goal['id'] in update.get('addressed_objective_ids',[]):
    goal['evidence_ids']=list(dict.fromkeys(goal['evidence_ids']+output['student_evidence_ids']))
    goal['observations'].append({'turn':turn_id,'assessment_suggestion':output['assessment'],'hint_level':output['hint_level'],'code_hash':ctx['code_hash']})
 course['last_code_hash']=ctx['code_hash']
 course['checkpoints'].append({'turn':turn_id,'goal':output['plan']['goal'],'next_step':output['plan']['next_step'],
  'open_questions':output['plan']['open_questions'],'student_evidence_ids':output['student_evidence_ids'],'code_hash':ctx['code_hash']})
 if output['teaching_action']=='ask_transfer':
  s['pending_transfer']={'question':output['transfer_question'],'code_hash':ctx['code_hash']}
  s['transfer_answer']=None
 s['turns'].append({'id':turn_id,'action':action,'strategy_version_id':t.get('strategy_version_id'),
  'code_hash':ctx['code_hash'],'loaded_skills':list(ctx['loaded_skills']),
  'created_at':time.time(),
  'provider':agent.metadata(),'phase_before':ctx['phase'],'tools':getattr(agent,'tool_trace',[]),'result':output})
 s['next_turn_id']=turn_id+1
 return output['reply']
