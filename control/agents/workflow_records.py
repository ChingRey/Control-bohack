"""Evidence-linked workflow proposals and reviewed rule revisions, independent of source tools."""
import copy
import json
import re
import time
import uuid
from . import workflow, providers, knowledge, project_safety

CONCEPTS=['页面','事件','状态','条件','数据','存储','接口']
def initialize(task):
 s=workflow.state(task)
 s.setdefault('concepts',{n:{'status':'unknown','evidence_ids':[]} for n in CONCEPTS})
 s.setdefault('rules',[]);s.setdefault('proposals',[]);s.setdefault('features',[])
 s.setdefault('mode','guided');s.setdefault('auto_organize',True)
 return s

def active_rules(task):
 return [copy.deepcopy(r) for r in initialize(task)['rules'] if r['status']=='active']

def candidates(task,result,source_ids):
 """Validate the whole response before changing stored records."""
 s=initialize(task);allowed=set(source_ids);rows=[]
 if not isinstance(result,dict) or not isinstance(result.get('items'),list) or len(result['items'])>10:raise ValueError('整理结果格式无效')
 for item in result['items']:
  if not isinstance(item,dict) or item.get('kind') not in (*workflow.MATERIALS,'rule','concept','rule_observation'):raise ValueError('未知整理记录')
  content=item.get('content');ids=item.get('evidence_ids');quotes=item.get('quotes')
  if not isinstance(content,str) or not content.strip() or len(content)>6000:raise ValueError('整理内容过长或为空')
  if not isinstance(ids,list) or not ids or any(type(i) is not int or i not in allowed for i in ids):raise ValueError('整理证据编号无效')
  if not isinstance(quotes,list) or not quotes or any(not isinstance(q,dict) or q.get('message_id') not in ids or not isinstance(q.get('quote'),str) or not q['quote'].strip() or q['quote'] not in task['messages'][q['message_id']]['content'] for q in quotes):raise ValueError('整理引用与原话不符')
  if set(ids)!={q['message_id'] for q in quotes}:raise ValueError('每个来源须有原话引用')
  if project_safety.SECRET.search(content):raise ValueError('材料建议包含疑似凭据，拒绝保存')
  row={k:copy.deepcopy(item[k]) for k in ('kind','content','evidence_ids','quotes')}
  if item['kind']=='rule':
   for k in ('title','when','limits'):
    if not isinstance(item.get(k),str) or not item[k].strip() or len(item[k])>500:raise ValueError('规则需标题、适用条件与边界')
    row[k]=item[k]
   replaces=item.get('replaces_id')
   if replaces and not any(r['id']==replaces for r in s['rules']):raise ValueError('被修订规则不存在')
   row['replaces_id']=replaces
   terms=set(knowledge._terms(row['title']+' '+row['content']))
   similar=[]
   for rule in active_rules(task):
    old=set(knowledge._terms(rule['title']+' '+rule['content']));score=len(terms&old)/max(1,len(terms|old))
    if score>=.3:similar.append({'id':rule['id'],'score':round(score,3)})
   row['similar_rules']=similar  # lexical hints; semantic equivalence remains a review decision.
  if item['kind']=='rule_observation':
   if not any(r['id']==item.get('rule_id') for r in s['rules']) or item.get('outcome') not in ('followed','missed','uncertain'):raise ValueError('规则观察无效')
   row.update(rule_id=item['rule_id'],outcome=item['outcome'],code_hash=task.get('project_hash'))
  if item['kind']=='concept':
   if item.get('concept') not in CONCEPTS or item.get('level') not in ('explained','practiced','independent_candidate'):raise ValueError('概念记录无效')
   row.update(concept=item['concept'],level=item['level'])
  row.update(id=str(uuid.uuid4()),status='pending_review',created_at=time.time(),base_revision=s['revision'],model_suggestion=True)
  if not any(old['kind']==row['kind'] and old['content']==row['content'] and old['evidence_ids']==row['evidence_ids'] for old in [*s['proposals'],*rows]):rows.append(row)
 s['proposals'].extend(rows)
 return rows

def organize(task,progress=lambda *a:None):
 from . import teaching
 config=providers.settings()
 if teaching.TeachingAgent().mode!='model':raise ValueError('请连接Teaching模型；不会用Mock冒充真实整理')
 eligible=[i for i,m in enumerate(task['messages']) if m.get('queue_status') not in ('queued','needs_retry')]
 selected=[];used=0
 for i in reversed(eligible):
  m=task['messages'][i];cost=len(m['content'])
  if used+cost>24000:break
  selected.append({'id':i,**m});used+=cost
 selected.reverse()
 packet={'messages':selected,'omitted_message_count':len(eligible)-len(selected),'materials':workflow.shared(task),'rules':active_rules(task),'behavior_records':task.get('behavior_records',[])[-10:],'concepts':initialize(task)['concepts'],'changes':[{'file':c['file'],'before':c.get('before','')[:2000],'after':c.get('after','')[:2000]} for c in task.get('changes',[])[-4:]],'project_hash':task.get('project_hash')}
 system='你是只读项目材料整理器，不修改源码，不调用Coding，不替学生确认。根据有编号的原始对话整理待审核建议。不要抄秘密或编造引用；只根据本次材料推断，缺证据就不提出。需求和设计决定不是已验证经验；能力观察只是待核实建议。返回JSON {"items":[]}，最多6项。每项kind为requirements/design/experiences/coverage/learner/rule/concept/rule_observation；rule_observation需rule_id和outcome（followed/missed/uncertain），只记录本版本的待核实遵守情况，不证明行为正确；content为精简文本；evidence_ids为来源整数数组；quotes为[{"message_id":整数,"quote":"对应原话的完整连续片段"}]。rule额外有title/when/limits/replaces_id（修订同义旧规则时用其id，否则null），优先修订旧项而非堆叠同义项。concept额外有concept（页面/事件/状态/条件/数据/存储/接口）和level（explained/practiced/independent_candidate），不能认证已掌握。不要重复已经整理过的建议。'
 req=providers.request(config,[{'role':'system','content':system},{'role':'user','content':json.dumps(packet,ensure_ascii=False)}],3000,json_mode=True)
 response=providers.normalize(config,teaching.request_model(req,{'attempts':0,'deadline':time.monotonic()+120},progress))
 text=response['choices'][0]['message'].get('content','').strip()
 if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0]
 return candidates(task,json.loads(text),[m['id'] for m in selected])

def review(task,body):
 s=initialize(task)
 row=next((r for r in s['proposals'] if r['id']==body.get('proposal_id')),None)
 if not row:raise ValueError('建议不存在')
 decision=body.get('decision')
 if row['status']!='pending_review':
  if row.get('decision')==decision:return row
  raise ValueError('建议已经处理')
 if decision not in ('accept','reject'):raise ValueError('审核操作无效')
 if decision=='accept':
  if body.get('expected_revision')!=s['revision']:raise ValueError('材料已变化，请查看当前内容后确认')
  content=body.get('content',row['content'])
  if not isinstance(content,str) or not content.strip() or len(content)>6000:raise ValueError('内容无效')
  if project_safety.SECRET.search(content):raise ValueError('内容包含疑似凭据，请移除后再保存')
  if row['kind']=='rule':
   target=body.get('replaces_id',row.get('replaces_id'))
   rule=next((r for r in s['rules'] if r['id']==target),None)
   if target and not rule:raise ValueError('被修订规则不存在')
   if not rule:
    if len(active_rules(task))>=15:raise ValueError('有效规则最多15条，请修订或停用旧规则')
    rule={'id':str(uuid.uuid4()),'revision':0,'history':[]};s['rules'].append(rule)
   elif rule['status']!='active' and len(active_rules(task))>=15:raise ValueError('有效规则最多15条，请先停用其他规则')
   else:rule['history'].append({k:copy.deepcopy(v) for k,v in rule.items() if k!='history'})
   rule.update(revision=rule['revision']+1,status='active',title=row['title'],content=content,when=row['when'],limits=row['limits'],evidence_ids=row['evidence_ids'],quotes=row['quotes'],verified=False)
   row['rule_id']=rule['id'];s['revision']+=1
  elif row['kind']=='rule_observation':
   rule=next(r for r in s['rules'] if r['id']==row['rule_id'])
   rule.setdefault('observations',[]).append({**copy.deepcopy(row),'student_reviewed':True,'verified_behavior':False});s['revision']+=1
  elif row['kind']=='concept':
   s['concepts'][row['concept']]={'status':row['level'],'evidence_ids':row['evidence_ids'],'model_suggestion':True,'verified_mastery':False};s['revision']+=1
  else:
   workflow.update(task,{'kind':row['kind'],'content':content,'expected_revision':s['revision'],'confirmed':True},'student')
 row.update(status='accepted' if decision=='accept' else 'rejected',decision=decision)
 return row

def rule_status(task,body):
 s=initialize(task);rule=next((r for r in s['rules'] if r['id']==body.get('rule_id')),None)
 if not rule or body.get('status') not in ('active','inactive'):raise ValueError('规则状态无效')
 if body['status']=='active' and rule['status']!='active' and len(active_rules(task))>=15:raise ValueError('有效规则最多15条')
 if body.get('expected_revision')!=s['revision']:raise ValueError('规则版本已变化')
 rule['history'].append({k:copy.deepcopy(v) for k,v in rule.items() if k!='history'})
 rule.update(status=body['status'],revision=rule['revision']+1);s['revision']+=1
 return rule


def feature(task,body,code_hash):
 s=initialize(task)
 if body.get('expected_revision')!=s['revision']:raise ValueError('工作流已变化，请刷新')
 action=body.get('action')
 if action=='create':
  title=body.get('title')
  if not isinstance(title,str) or not title.strip() or len(title)>500:raise ValueError('请描述一个当前功能')
  row={'id':str(uuid.uuid4()),'title':title.strip(),'status':'planned','events':[]};s['features'].append(row);s['current_feature_id']=row['id']
 else:
  row=next((r for r in s['features'] if r['id']==body.get('feature_id')),None)
  if not row:raise ValueError('功能记录不存在')
  if action=='select':s['current_feature_id']=row['id']
  elif action=='accept':
   explanation=body.get('explanation')
   if not isinstance(explanation,str) or not explanation.strip() or len(explanation)>4000:raise ValueError('请说明保留了什么、改变了什么，以及怎样回归验证')
   evidence=[r for key in ('behavior_records','browser_records','execution_records') for r in task.get(key,[]) if r.get('hash')==code_hash and (r.get('result')=='passed' or r.get('passed') is True)]
   if not evidence:raise ValueError('请先记录当前代码版本的实际验证结果；仍可继续聊天或修复')
   row.update(status='accepted',accepted_hash=code_hash,student_explanation=explanation,evidence_ids=[r['id'] for r in evidence],verified_mastery=False)
  else:raise ValueError('功能操作无效')
 row['events'].append({'action':action,'code_hash':code_hash});s['revision']+=1
 return row
