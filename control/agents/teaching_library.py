"""Offline, reviewed lesson selection. Loading is provenance, never mastery evidence."""
import copy
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from . import workflow

ASSET=Path(__file__).resolve().parent/'teaching_assets/library/catalog.json'
MAX_PACKET_CHARS=11000
MAX_LESSONS=2
MAX_SOURCES=6
STAGE_DEFAULTS={0:['L01','L02'],1:['L03','L04','L05','L07','L09'],2:['L12','L13','L14','L15','L16'],3:['L17','L18','L19'],4:['L20','L16','L21']}
POLICY_IDS=('R01','R02','R04','R05','R08','R37')

def size(value):return len(json.dumps(value,ensure_ascii=False,sort_keys=True))

@lru_cache(maxsize=1)
def catalog():
 value=json.loads(ASSET.read_text(encoding='utf-8'))
 unsigned={k:v for k,v in value.items() if k!='content_hash'}
 digest=hashlib.sha256(json.dumps(unsigned,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 if value.get('schema_version')!=1 or digest!=value.get('content_hash'):raise ValueError('教学资料版本校验失败')
 source_ids={s['id'] for s in value['sources']};lesson_ids={l['id'] for l in value['lessons']}
 if len(source_ids)!=len(value['sources']) or len(lesson_ids)!=len(value['lessons']):raise ValueError('教学资料编号重复')
 for s in value['sources']:
  if not s['url'].startswith('https://'):raise ValueError('教学来源必须为HTTPS链接')
 for lesson in value['lessons']:
  if not set(lesson['source_ids'])<=source_ids or lesson.get('runtime_enabled') is not True:raise ValueError('教学课卡引用无效')
 return value

def preferences(task):
 return task.get('workflow',{}).get('teaching_resources',{'focus_lesson_id':None,'deferred_lesson_ids':[]})

def choose(task,lesson_id,choice):
 if choice not in ('learn','later','auto'):raise ValueError('选学操作无效')
 if choice!='auto' and lesson_id not in {l['id'] for l in catalog()['lessons']}:raise ValueError('未知教学主题')
 s=workflow.state(task);prefs=s.setdefault('teaching_resources',{'focus_lesson_id':None,'deferred_lesson_ids':[]})
 if choice=='learn':
  prefs['focus_lesson_id']=lesson_id
  prefs['deferred_lesson_ids']=[x for x in prefs['deferred_lesson_ids'] if x!=lesson_id]
  prefs.setdefault('deferred_at',{}).pop(lesson_id,None)
 elif choice=='later':
  if lesson_id not in prefs['deferred_lesson_ids']:prefs['deferred_lesson_ids'].append(lesson_id)
  prefs.setdefault('deferred_at',{})[lesson_id]=len(task.get('messages',[]))
  if prefs['focus_lesson_id']==lesson_id:prefs['focus_lesson_id']=None
 else:prefs['focus_lesson_id']=None
 s['revision']+=1

def question(task,action):
 messages=[m for m in task.get('messages',[]) if m.get('role')=='user' and m.get('queue_status') not in ('queued','needs_retry')]
 if action in ('checkpoint','review'):
  event=(task.get('coding_checkpoints') or [{}])[-1]
  return str(event.get('task_description',''))[:12000]
 row=next((m for m in reversed(messages) if m.get('channel')=='teaching'),None)
 if row is None:row=messages[-1] if messages else {}
 return row.get('content','')[:12000]

def matches(text,token):
 return bool(re.search(r'(?<![a-z0-9_])'+re.escape(token)+r'(?![a-z0-9_])',text)) if token.isascii() else token in text

def select(task,action='message'):
 data=catalog();stage=task.get('workflow',{}).get('stage',0);mode=task.get('workflow',{}).get('mode','guided')
 prefs=preferences(task);focus=prefs.get('focus_lesson_id');deferred=set(prefs.get('deferred_lesson_ids',[]))
 text=question(task,action).lower().strip();recent=[]
 for turn in task.get('teaching',{}).get('turns',[])[-3:]:recent.extend(turn.get('teaching_library',{}).get('lesson_ids',[]))
 if re.search(r'先不学|不想学|暂时不学|不要讲课|只想开发|先暂停讲解|skip lesson',text):return [],'student_declined'
 if re.fullmatch(r'(?:我)?(?:懂了|明白了|会了)[，,。！!\s]*(?:继续(?:开发)?(?:吧)?|谢谢)?[。！!]*',text):return [],'conversation_without_new_lesson'
 if text in ('你好','您好','hi','hello','谢谢','好的','谢谢你','我懂了','懂了','继续','继续开发','可以继续') and action not in ('lesson','checkpoint','review'):return [],'conversation_without_new_lesson'
 ranking=[]
 direct=bool(re.search(r'是什么|怎么|为什么|解释|讲讲|不懂|看不懂|what|how|explain',text))
 for card in data['lessons']:
  hits=[word for word in card['keywords'] if matches(text,word)]
  score=len(hits)*5
  if focus==card['id']:score+=100
  deferred_at=prefs.get('deferred_at',{}).get(card['id'])
  reopened=isinstance(deferred_at,int) and any(i>=deferred_at and m.get('role')=='user' and m.get('channel')=='teaching' and m.get('queue_status') not in ('queued','needs_retry') and m.get('content','').lower().strip()==text for i,m in enumerate(task.get('messages',[])))
  if card['id'] in deferred and focus!=card['id'] and not (hits and direct and reopened):continue
  if action in ('checkpoint','review') and task.get('files') and card['id'] in ('L12','L13'):score+=12
  if action in ('checkpoint','review') and not task.get('files') and card['id'] in ('L01','L02'):score+=12
  if task.get('safety_report',{}).get('publication_blocked') and card['id']=='L18' and mode=='guided':score+=40
  if score:
   score+=int(card['stage']==stage)
   ranking.append((score,card['id'],card))
 ranking.sort(key=lambda r:(-r[0],r[1]))
 selected=[r[2] for r in ranking[:MAX_LESSONS]]
 if selected:return selected,'explicit_focus' if focus and selected[0]['id']==focus else 'current_question'
 if mode=='free':return [],'free_mode_without_topic'
 defaults=STAGE_DEFAULTS.get(stage,STAGE_DEFAULTS[0])
 for lesson_id in defaults:
  if lesson_id in deferred or lesson_id in recent:continue
  card=next(c for c in data['lessons'] if c['id']==lesson_id)
  selected.append(card)
  break
 return selected,'stage_suggestion' if selected else 'no_new_topic_needed'

def packet(task,action='message',budget=MAX_PACKET_CHARS):
 data=catalog();cards,reason=select(task,action);remaining=min(MAX_PACKET_CHARS,max(0,budget))
 result={'revision':data['revision'],'content_hash':data['content_hash'],'selection_reason':reason,'lessons':[],'sources':[],
         'notice':'课卡活动是候选建议，不是实际操作或学生证据；加载不证明采用、理解或掌握。','policy_source_ids':list(POLICY_IDS)}
 source_map={s['id']:s for s in data['sources']}
 for card in cards:
  packed={k:copy.deepcopy(card[k]) for k in ('id','revision','title','concept_explanation','illustrative_example','suggested_checks','main_question','student_activity','evidence_to_seek','common_misconception','transfer_prompt','source_ids')}
  proposed=copy.deepcopy(result);proposed['lessons'].append(packed)
  ids=list(dict.fromkeys(r for l in proposed['lessons'] for r in l['source_ids']))[:MAX_SOURCES]
  proposed['sources']=[copy.deepcopy(source_map[r]) for r in ids]
  if size(proposed)>remaining:break
  result=proposed
 if cards and not result['lessons']:result['selection_reason']='context_budget_exhausted'
 if size(result)>remaining:return {}
 return result

def trace(value,submitted=False):
 source_map={s['id']:s for s in catalog()['sources']}
 return {'revision':value.get('revision',catalog()['revision']),'content_hash':value.get('content_hash',catalog()['content_hash']),'lesson_ids':[c['id'] for c in value.get('lessons',[])],
         'source_ids':[s['id'] for s in value.get('sources',[])],'lessons':[{k:c[k] for k in ('id','revision','title')} for c in value.get('lessons',[])],'sources':[{k:s[k] for k in ('id','title','url')} for s in value.get('sources',[])],'policy_sources':[{k:source_map[r][k] for k in ('id','title','url')} for r in value.get('policy_source_ids',POLICY_IDS) if r in source_map],'selection_reason':value.get('selection_reason'),
         'policy_source_ids':list(value.get('policy_source_ids',POLICY_IDS)),'submitted_to_model':submitted,'application_verified':False,'mastery_certified':False}

def view(task):
 data=catalog();cards,reason=select(task)
 last_turn=next((turn for turn in reversed(task.get('teaching',{}).get('turns',[])) if turn.get('teaching_library')),None)
 last={**copy.deepcopy(last_turn['teaching_library']),'turn_id':last_turn['id']} if last_turn else None
 return {'revision':data['revision'],'preferences':copy.deepcopy(preferences(task)),
         'topics':[{k:c[k] for k in ('id','title','stage')} for c in data['lessons']],
         'suggested_lesson_ids':[c['id'] for c in cards],'selection_reason':reason,'last_turn':copy.deepcopy(last),
         'sources':[{k:s[k] for k in ('id','title','url')} for s in data['sources']]}

def organizer_context(task):
 last=next((turn.get('teaching_library') for turn in reversed(task.get('teaching',{}).get('turns',[])) if turn.get('teaching_library')),None)
 return {'guidance':catalog()['organizer_guidance'],'last_teaching_resources':copy.deepcopy(last),
         'notice':'资料来源不是项目事实或学生证据；evidence_ids仍只能指向真实原话。'}


def metadata():
 data=catalog()
 return {'revision':data['revision'],'content_hash':data['content_hash'],'lesson_count':len(data['lessons']),'source_count':len(data['sources']),'max_lessons_per_turn':MAX_LESSONS,'effectiveness_validated':False}
