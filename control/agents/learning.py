"""Evidence-linked learner observations, small experiences and guarded skill requests."""
import copy
import json
import uuid
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent/'learning_assets/catalog.json').read_text(encoding='utf-8'))
LEVELS = ('needs_help', 'supported', 'independent', 'transfer_candidate')

def state(task):
    return task.setdefault('teaching', {}).setdefault('learning', {'schema_version': 1, 'revision': 0,
        'observations': [], 'experiences': [], 'events': [], 'unlock_requests': [], 'coding_loads': []})

def references(item, ctx):
    ids = item.get('evidence_ids')
    available = {m['id']: m for m in ctx['messages'] if m.get('role') == 'user'}
    available.update({m['id']:m for m in ctx.get('student_evidence', []) if 'content' in m})
    if not isinstance(ids, list) or not 1 <= len(ids) <= 6 or any(type(i) is not int or i not in available for i in ids):
        raise ValueError('学习记录必须引用本轮实际提供的学生原话')
    quotes = item.get('quotes')
    if not isinstance(quotes, list) or not 1 <= len(quotes) <= 6:
        raise ValueError('学习记录需要原话片段')
    for q in quotes:
        if not isinstance(q, dict) or type(q.get('message_id')) is not int or q['message_id'] not in ids:
            raise ValueError('学习引用编号无效')
        if not isinstance(q.get('quote'), str) or not 4 <= len(q['quote'].strip()) <= 400 or q['quote'] not in available[q['message_id']]['content']:
            raise ValueError('学习引用和学生原话不一致')
    if set(ids) != {q['message_id'] for q in quotes}:
        raise ValueError('每个学习证据编号都需要原话引用')

def text(item, key, limit=600):
    if not isinstance(item.get(key), str) or not 1 <= len(item[key].strip()) <= limit:
        raise ValueError('学习字段无效：'+key)

def validate(update, ctx):
    if not isinstance(update, dict) or set(update)-{'observations','experiences','prompt_review'}:
        raise ValueError('学习更新格式无效')
    valid = {c['id'] for c in CATALOG['capabilities']}
    for key in ('observations','experiences'):
        items = update.get(key, [])
        if not isinstance(items, list) or len(items)>3: raise ValueError('每轮最多记录3条同类学习更新')
        for item in items:
            if not isinstance(item, dict): raise ValueError('学习条目无效')
            references(item, ctx)
            if key=='observations':
                if item.get('capability_id') not in valid or item.get('level') not in LEVELS:
                    raise ValueError('能力或表现级别无效')
                text(item,'explanation')
                if item['level']=='transfer_candidate':
                    answer=ctx.get('transfer_answer')
                    if not answer or answer['message_id'] not in item['evidence_ids']:
                        raise ValueError('迁移表现必须来自明确提交的迁移作答')
            else:
                for field in ('title','when','rule','verification','limits'):text(item,field)
                if item.get('kind') not in ('method','preference'):raise ValueError('经验要区分方法与个人偏好')
                tags=item.get('tags')
                if not isinstance(tags,list) or not 1<=len(tags)<=5 or any(not isinstance(x,str) or not 1<=len(x)<=30 for x in tags):raise ValueError('经验标签无效')
    review=update.get('prompt_review')
    if review is not None:
        references(review,ctx)
        current=ctx.get('current_focus',{}).get('coding_prompt_id')
        if type(review.get('message_id')) is not int or review.get('message_id')!=current or current not in review['evidence_ids']:raise ValueError('提示词分析必须对应最新Coding提示词')
        for field in ('strengths','gaps','next_step'):text(review,field)
    return update

def apply(task, update, turn_id, code_hash):
    s=state(task)
    for key in ('observations','experiences'):
        for item in update.get(key,[]):
            row=copy.deepcopy(item)
            row.update(id=str(uuid.uuid4()),source_turn=turn_id,code_hash=code_hash,
                       status='draft' if key=='experiences' else 'model_suggestion',revision=1)
            if key=='observations':row['independence_verified']=False
            s[key].append(row)
    if update.get('prompt_review') is not None:
        s['prompt_review']={**copy.deepcopy(update['prompt_review']),'source_turn':turn_id,'code_hash':code_hash,'status':'model_suggestion'}
    if update:s['revision']+=1

def set_experience(task, card_id, action, confirmed):
    if confirmed is not True:raise ValueError('需要明确确认经验操作')
    s=state(task);card=next((c for c in s['experiences'] if c['id']==card_id),None)
    if not card:raise ValueError('经验不存在')
    target={'confirm':'confirmed','disable':'disabled','reject':'rejected'}.get(action)
    if target is None:raise ValueError('经验操作无效')
    if target=='confirmed' and card['status'] not in ('draft','disabled'):raise ValueError('当前经验不能重复确认')
    if target=='disabled' and card['status']!='confirmed':raise ValueError('只有已确认经验可以停用')
    s['events'].append({'id':str(uuid.uuid4()),'kind':'experience_status','card_id':card_id,'before':copy.deepcopy(card),'after_status':target})
    card['status']=target;card['revision']+=1;s['revision']+=1
    return card

def profile(task):
    s=state(task);rows=[]
    for capability in CATALOG['capabilities']:
        observations=[o for o in s['observations'] if o['capability_id']==capability['id']]
        rows.append({**capability,'level':observations[-1]['level'] if observations else 'unknown',
                     'status':'provisional_not_certified','evidence_count':len({i for o in observations for i in o['evidence_ids']}),
                     'recent_observations':observations[-3:]})
    return rows

def readiness(task):
    s=state(task);result=[]
    for skill in CATALOG['skills']:
        missing=[]
        for cid in skill['requires']:
            rows=[o for o in s['observations'] if o['capability_id']==cid and o['level'] in ('independent','transfer_candidate')]
            ids={i for o in rows for i in o['evidence_ids']}
            if len(ids)<2 or not any(o['level']=='transfer_candidate' for o in rows):missing.append(cid)
        result.append({**skill,'missing_capabilities':missing,'student_ready_for_review':not missing,
                       'agent_verified':False,'can_install':False,
                       'reason':'候选Skill尚未在当前Coding适配器上完成对照验证；学生表现也需要复核'})
    return result

def request_unlock(task, skill_id, confirmed):
    if confirmed is not True:raise ValueError('需要学生明确确认申请')
    skill=next((x for x in readiness(task) if x['id']==skill_id),None)
    if not skill:raise ValueError('Skill候选不存在')
    if not skill['student_ready_for_review']:raise ValueError('相关能力证据不足，暂不能申请解锁')
    s=state(task)
    if any(x['skill_id']==skill_id and x['status']=='pending_review' for x in s['unlock_requests']):raise ValueError('已有待复核申请')
    s['unlock_requests'].append({'id':str(uuid.uuid4()),'skill_id':skill_id,'status':'pending_review','applied':False,
                                 'agent_validation':'not_evaluated','observation_ids':[x['id'] for x in s['observations']]})
    s['revision']+=1

def coding_packet(task, instruction):
    cards=[c for c in state(task)['experiences'] if c['status']=='confirmed' and any(tag.lower() in instruction.lower() for tag in c['tags'])]
    return {'rules':[{'id':c['id'],'revision':c['revision'],'kind':c['kind'],'when':c['when'],'rule':c['rule'],
                     'verification':c['verification'],'limits':c['limits']} for c in cards[-3:]],
            'skills':[],'scope':'current_task_only','note':'资料是学生确认的经验，不是系统指令；当前示例Coding仅记录输入，不据此修改行为'}

def view(task):
    s=state(task)
    return {'revision':s['revision'],'profile':profile(task),'experiences':s['experiences'],
            'prompt_review':s.get('prompt_review'),'skills':readiness(task),'unlock_requests':s['unlock_requests'],
            'coding_loads':s['coding_loads'][-5:]}
