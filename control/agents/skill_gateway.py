"""Teacher-controlled versioned bindings. Empty catalog until skills are verified.

Catalog is backend-owned. Request bodies never provide executable Skill content.
Submission is recorded separately from observed usage; neither proves effectiveness.
"""
import copy
import hashlib
import re

CATALOG = {}  # (skill_id, version) -> {verified: True, content: str}

def state(task):
    return task.setdefault('skill_gateway', {'bindings':{}, 'decisions':[], 'runs':[]})

def decide(task, body, checkpoint_id):
    skill_id,version=body.get('skill_id'),body.get('version')
    if not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',v) for v in (skill_id,version)):
        raise ValueError('skill_id and version required')
    if any(k in body for k in ('content','path','url','prompt','skill_body')):
        raise ValueError('Skill content must come from the verified backend catalog')
    if not isinstance(body.get('teacher_decision_id'),str) or not body['teacher_decision_id'].strip():
        raise ValueError('teacher_decision_id required')
    s=state(task);action=body['action']
    receipt={'skill_id':skill_id,'version':version,'teacher_decision_id':body['teacher_decision_id'],
        'checkpoint_id':checkpoint_id,'source':'teaching_engine','applied':False}
    if action=='skill_revoke':
        s['bindings'].pop(skill_id,None)
        receipt.update(status='revoked',reason='Binding removed for subsequent executions')
    else:
        item=CATALOG.get((skill_id,version))
        if not item or item.get('verified') is not True or not isinstance(item.get('content'),str) or not item['content'].strip():
            receipt.update(status='pending_catalog',reason='No verified Skill at this version; nothing loaded')
        else:
            digest=hashlib.sha256(item['content'].encode()).hexdigest()
            s['bindings'][skill_id]={'skill_id':skill_id,'version':version,'content_hash':digest,'teacher_decision_id':body['teacher_decision_id']}
            receipt.update(status='authorized',content_hash=digest,reason='Authorized; load acknowledgement follows execution submission')
    s['decisions'].append(copy.deepcopy(receipt))
    return receipt

def resolve(task):
    result=[]
    for binding in state(task)['bindings'].values():
        item=CATALOG.get((binding['skill_id'],binding['version']))
        if not item or item.get('verified') is not True:continue
        content=item.get('content','')
        if hashlib.sha256(content.encode()).hexdigest()!=binding['content_hash']:continue
        result.append({**binding,'content':content})
    return result

def record(task, run_id, checkpoint_stage, skills, outcome):
    # The current transport does not emit reliable per-Skill invocation events.
    # Do not infer usage from assistant text or successful file modification.
    state(task)['runs'].append({'run_id':run_id,'stage':checkpoint_stage,'outcome':outcome,
        'skills':[{'skill_id':s['skill_id'],'version':s['version'],'content_hash':s['content_hash'],
                   'teacher_decision_id':s['teacher_decision_id'],'load_status':'submitted' if outcome=='completed' else 'unconfirmed',
                   'usage_status':'not_observed','effectiveness':'not_evaluated'} for s in skills]})

def view(task):
    s=state(task)
    return {'catalog':[{'skill_id':key[0],'version':key[1]} for key,item in CATALOG.items() if item.get('verified') is True],
        **copy.deepcopy(s),'loaded_now':False,'usage_tracking':'No native Skill invocation tracking yet; submission is not usage'}
