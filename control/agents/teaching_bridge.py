"""Durable pull outbox. Teaching never writes project files through this API."""
import copy
import hashlib
import json
import uuid
from . import coding_workflow, skill_gateway

def publish(task, instruction, output, changes, files):
    if not task.get('plan'):
        return
    state=task.setdefault('teaching_bridge', {'events':[], 'requests':{}})
    state['events'].append({
        'session_id':task['id'], 'checkpoint_id':str(uuid.uuid4()),
        'stage':task['step'], 'task_description':instruction,
        'user_requirement':next((m['content'] for m in reversed(task['messages']) if m['channel']=='coding' and m['role']=='user'), instruction),
        'agent_output':output, 'plan':list(task['plan']),
        'project_evidence':{'changes':copy.deepcopy(changes),
            'runtime_results':copy.deepcopy(task.get('runtime_observations',[])),
            'test_records':copy.deepcopy(task.get('checks',[])),
            'file_hashes':{n:hashlib.sha256(s.encode()).hexdigest() for n,s in files.items()},
            'files_url':'/api/tasks/'+task['id']+'/bridge/files',
            'evidence_note':'Browser observations and static checks are not verified behavioral tests.'},
        'status':'waiting_teaching', 'receipt':None})

def events(task):
    return copy.deepcopy(task.get('teaching_bridge',{}).get('events',[]))

def command(task, body):
    state=task.setdefault('teaching_bridge', {'events':[], 'requests':{}})
    request_id=body.get('request_id')
    if not isinstance(request_id,str) or not 1<=len(request_id)<=120:
        raise ValueError('request_id required (1-120 characters)')
    digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    old=state['requests'].get(request_id)
    if old:
        if old['digest']!=digest:raise ValueError('request_id payload conflict')
        return copy.deepcopy(old['receipt']), None
    event=next((e for e in state['events'] if e['checkpoint_id']==body.get('checkpoint_id')),None)
    if not event:raise ValueError('Unknown checkpoint_id')
    if event['stage']!=task['step'] or event['status']!='waiting_teaching':
        raise ValueError('Checkpoint is stale or already resumed')
    action=body.get('action')
    instruction=None
    if action=='modify':
        if body.get('student_confirmed') is not True:raise ValueError('Student confirmation required')
        instruction=body.get('instruction')
        if not isinstance(instruction,str) or not instruction.strip() or len(instruction)>12000:raise ValueError('Invalid instruction')
        event['status']='revision_requested'
    elif action=='resume':
        coding_workflow.accept_phase(task)
        event['status']='resumed'
        if task['step']<len(task['plan']):instruction=task['plan'][task['step']]
    elif action in ('skill_unlock','skill_revoke'):
        receipt={'request_id':request_id,'checkpoint_id':event['checkpoint_id'], **skill_gateway.decide(task,body,event['checkpoint_id'])}
        state['requests'][request_id]={'digest':digest,'receipt':receipt}
        return copy.deepcopy(receipt),None
    else:raise ValueError('Unknown action')
    receipt={'request_id':request_id,'checkpoint_id':event['checkpoint_id'],'status':'accepted','action':action,'execution_status':'pending' if instruction else 'not_needed'}
    event['receipt']=receipt
    state['requests'][request_id]={'digest':digest,'receipt':receipt}
    return copy.deepcopy(receipt),instruction
