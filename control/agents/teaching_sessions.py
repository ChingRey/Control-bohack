"""Post-teaching distillation. Teacher writes knowledge records, never source files."""
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from . import learning, knowledge

def now():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

class MockDistiller:
    def extract(self, packet):
        students=[m for m in packet['dialogue'] if m['role']=='user']
        if not students:return {'mode':'mock','items':[]}
        source=students[-1]
        return {'mode':'mock','items':[{'type':'project_fact','title':'Mock: post-lesson experience',
            'content':'Mock placeholder: review the applicable project context and verify behavior before reusing this experience.',
            'when':'Mock scenario only','limits':'Not extracted by a real teaching model; not for Coding retrieval.',
            'evidence_ids':[source['id']],
            'quotes':[{'message_id':source['id'],'quote':source['content'][:400]}]}]}

DISTILLER=MockDistiller()

def open_session(task, body):
    sessions=task.setdefault('teaching_sessions',[])
    request_id=body.get('request_id')
    if not isinstance(request_id,str) or not 1<=len(request_id)<=120:raise ValueError('request_id required')
    previous=next((s for s in sessions if s['open_request_id']==request_id),None)
    if previous:return copy.deepcopy(previous)
    if any(s['status']=='active' for s in sessions):raise ValueError('An active teaching session already exists')
    row={'teaching_session_id':str(uuid.uuid4()),'session_id':task['id'],'open_request_id':request_id,
         'status':'active','message_start':len(task['messages']) if sessions else 0,'created_at':now()}
    sessions.append(row)
    return copy.deepcopy(row)

def finish(task, body, files):
    request_id=body.get('request_id')
    if not isinstance(request_id,str) or not 1<=len(request_id)<=120:raise ValueError('request_id required')
    session=next((s for s in task.get('teaching_sessions',[]) if s['teaching_session_id']==body.get('teaching_session_id')),None)
    if not session:raise ValueError('Unknown teaching_session_id')
    fingerprint=digest(body)
    if session['status']=='completed':
        if session['finish_request_id']!=request_id or session['finish_fingerprint']!=fingerprint:
            raise ValueError('Teaching session already completed')
        return copy.deepcopy(session['result'])
    if body.get('confirmed') is not True:raise ValueError('Explicit teaching completion confirmation required')
    dialogue=[{'id':i,**m} for i,m in enumerate(task['messages'])
        if i>=session['message_start'] and m.get('channel') in ('coding','teaching')]
    packet={'session_id':task['id'],'teaching_session_id':session['teaching_session_id'],
            'dialogue':copy.deepcopy(dialogue),'files':copy.deepcopy(files),
            'plan':list(task.get('plan',[])),'code_hash':knowledge.code_hash(files)}
    extracted=DISTILLER.extract(packet)
    if not isinstance(extracted,dict) or extracted.get('mode') not in ('mock','model'):
        raise ValueError('Invalid distillation adapter result')
    items=extracted.get('items')
    if not isinstance(items,list) or len(items)>10:raise ValueError('At most 10 knowledge candidates')
    sources={m['id']:m for m in dialogue};rows=[]
    for item in items:
        if not isinstance(item,dict) or item.get('type') not in knowledge.SEARCHABLE_TYPES:raise ValueError('Invalid knowledge type')
        for key,limit in (('title',200),('content',600),('when',200),('limits',200)):
            if not isinstance(item.get(key),str) or not 1<=len(item[key].strip())<=limit:raise ValueError('Invalid '+key)
        ids=item.get('evidence_ids');quotes=item.get('quotes')
        if not isinstance(ids,list) or not 1<=len(ids)<=10 or any(type(i) is not int or i not in sources for i in ids):
            raise ValueError('Invalid source message IDs')
        if not isinstance(quotes,list) or not 1<=len(quotes)<=10:raise ValueError('Source quotes required')
        for q in quotes:
            if not isinstance(q,dict) or q.get('message_id') not in ids or not isinstance(q.get('quote'),str) or not q['quote'].strip() or q['quote'] not in sources[q['message_id']]['content']:
                raise ValueError('Quote does not match original dialogue')
        if set(ids)!={q['message_id'] for q in quotes}:raise ValueError('Each source needs a matching quote')
        row=copy.deepcopy(item)
        row['content']=item['content']+'\n适用场景：'+item['when']+'\n使用边界：'+item['limits']
        row.update(id=str(uuid.uuid4()),source_turn=-1,code_hash=packet['code_hash'],revision=1,created_at=now(),verified=False,
            status='mock_only' if extracted['mode']=='mock' else 'pending_review',origin='post_teaching_distillation',
            teaching_session_id=session['teaching_session_id'],mode=extracted['mode'])
        rows.append(row)
    state=learning.state(task)
    state['knowledge_candidates'].extend(rows)
    if rows:state['revision']+=1
    result={'session_id':task['id'],'teaching_session_id':session['teaching_session_id'],'status':'completed',
        'mode':extracted['mode'],'candidate_ids':[r['id'] for r in rows],
        'knowledge_status':'mock_only' if extracted['mode']=='mock' else 'pending_review',
        'source_message_ids':list(sources),'dialogue_hash':digest(dialogue),'code_hash':packet['code_hash'],
        'coding_knowledge_applied':False}
    session.update(status='completed',completed_at=now(),finish_request_id=request_id,finish_fingerprint=fingerprint,result=result)
    return copy.deepcopy(result)
