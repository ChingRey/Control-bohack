"""Reviewed, task-scoped project knowledge for OpenCode retrieval.

Teaching may propose records, but only reviewed records are searchable by Coding.
The SQLite table is a retrieval index; the task's learning record remains the
authoritative versioned history.
"""
import json
import hashlib
import re
import sqlite3


SEARCHABLE_TYPES = {'project_fact', 'observed_failure', 'verified_pattern'}
ALL_TYPES = SEARCHABLE_TYPES | {'skill_candidate'}


def code_hash(files):
    return hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_items (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        quotes_json TEXT NOT NULL,
        source_turn INTEGER NOT NULL,
        code_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        revision INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        review_note TEXT
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_task_status ON knowledge_items(task_id,status,type)')


def sync_task(conn, task):
    """Mirror task-owned candidates into the retrieval table in the same save transaction."""
    learning = task.get('teaching', {}).get('learning', {})
    for row in learning.get('knowledge_candidates', []):
        conn.execute('''INSERT OR REPLACE INTO knowledge_items
            (id,task_id,type,title,content,evidence_json,quotes_json,source_turn,code_hash,status,
             revision,created_at,reviewed_at,reviewed_by,review_note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                row['id'], task['id'], row['type'], row['title'], row['content'],
                json.dumps(row['evidence_ids'], ensure_ascii=False),
                json.dumps(row['quotes'], ensure_ascii=False), row['source_turn'],
                row['code_hash'], row['status'], row['revision'], row['created_at'],
                row.get('reviewed_at'), row.get('reviewed_by'), row.get('review_note')))


def list_task(conn, task_id):
    rows = conn.execute('''SELECT id,task_id,type,title,content,evidence_json,quotes_json,source_turn,
        code_hash,status,revision,created_at,reviewed_at,reviewed_by,review_note
        FROM knowledge_items WHERE task_id=? ORDER BY created_at DESC''', (task_id,)).fetchall()
    fields = ('id','task_id','type','title','content','evidence_json','quotes_json','source_turn',
              'code_hash','status','revision','created_at','reviewed_at','reviewed_by','review_note')
    result=[]
    for values in rows:
        item=dict(zip(fields,values))
        item['evidence_ids']=json.loads(item.pop('evidence_json'))
        item['quotes']=json.loads(item.pop('quotes_json'))
        result.append(item)
    return result


def _terms(text):
    text=text.lower()
    words=re.findall(r'[a-z0-9_]+',text)
    cjk=''.join(re.findall(r'[\u3400-\u9fff]',text))
    # Character bigrams make basic retrieval useful for Chinese without embeddings.
    words.extend(cjk[i:i+2] for i in range(max(0,len(cjk)-1)))
    if len(cjk)==1:words.append(cjk)
    return list(dict.fromkeys(words))


def search(conn, task_id, query, current_code_hash, limit=3):
    if not isinstance(query,str) or not query.strip() or len(query)>12000:
        raise ValueError('Knowledge search query must contain 1 to 12000 characters')
    if type(limit) is not int or not 1<=limit<=5:
        raise ValueError('Knowledge search limit must be from 1 to 5')
    terms=_terms(query)
    if not terms:return []
    rows=conn.execute('''SELECT id,type,title,content,evidence_json,quotes_json,source_turn,code_hash,revision
        FROM knowledge_items WHERE task_id=? AND status='approved' AND type IN
        ('project_fact','observed_failure','verified_pattern') ORDER BY reviewed_at DESC,created_at DESC''',
        (task_id,)).fetchall()
    found=[]
    for row in rows:
        item=dict(zip(('id','type','title','content','evidence_json','quotes_json','source_turn','code_hash','revision'),row))
        haystack=' '.join((item['title'],item['content'])).lower()
        matched=[term for term in terms if term in haystack]
        score=len(matched)/len(terms)
        # Long conversational queries contain filler; require meaningful overlap
        # and rank by coverage instead of requiring every character pair to match.
        if score < (0.22 if len(terms)>6 else 0.4):continue
        found.append({
            'id':item['id'],'type':item['type'],'title':item['title'],
            'content':item['content'][:1200],
            'evidence_ids':json.loads(item['evidence_json']),
            'quotes':json.loads(item['quotes_json']),
            'source_turn':item['source_turn'],'code_hash':item['code_hash'],
            'revision':item['revision'],'relevance':round(score,3),
            'stale_for_code':item['code_hash']!=current_code_hash,
        })
    return sorted(found,key=lambda x:(x['relevance'],x['source_turn']),reverse=True)[:limit]


def add_manual(task, title, content, current_code_hash, confirmed):
    """Record an explicit human-authored experimental rule, without claiming verification."""
    if confirmed is not True:raise ValueError('Explicit confirmation is required')
    for value, limit in ((title,120),(content,4000)):
        if not isinstance(value,str) or not value.strip() or len(value)>limit:
            raise ValueError('Title (1-120) and content (1-4000) are required')
    from datetime import datetime, timezone
    import uuid
    from . import learning
    s=learning.state(task)
    evidence_id=len(task.setdefault('messages',[]))
    task['messages'].append({'channel':'teaching','role':'user',
        'content':'[Manual project knowledge] '+title.strip()+'\n'+content.strip()})
    row={'id':'manual-'+uuid.uuid4().hex,'type':'project_fact','title':title.strip(),
         'content':content.strip(),'evidence_ids':[evidence_id],
         'quotes':[{'message_id':evidence_id,'quote':content.strip()}],
         'source_turn':-1,'code_hash':current_code_hash,'status':'pending_review',
         'revision':1,'created_at':datetime.now(timezone.utc).isoformat(),
         'origin':'manual_experiment','verified':False}
    s.setdefault('knowledge_candidates',[]).append(row)
    s['revision']+=1
    return row


def review(task, candidate_id, decision, reviewer, note=''):
    if decision not in ('approve','reject','withdraw'):
        raise ValueError('decision must be approve, reject, or withdraw')
    if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>120:
        raise ValueError('reviewer is required')
    if not isinstance(note,str) or len(note)>1000:
        raise ValueError('review note is too long')
    learning=task.get('teaching',{}).get('learning',{})
    row=next((x for x in learning.get('knowledge_candidates',[]) if x['id']==candidate_id),None)
    if row is None:raise ValueError('Knowledge candidate not found')
    if decision=='withdraw':
        if row['status']!='approved':raise ValueError('Only approved knowledge can be withdrawn')
        target='withdrawn'
    else:
        if row['status']!='pending_review' and not (row.get('origin')=='manual_experiment' and row['status']=='withdrawn' and decision=='approve'):
            raise ValueError('Only pending knowledge or withdrawn manual knowledge can be approved')
        target={'approve':'approved','reject':'rejected'}[decision]
    from datetime import datetime, timezone
    before=row['status'];row.update(status=target,revision=row['revision']+1,
        reviewed_at=datetime.now(timezone.utc).isoformat(),reviewed_by=reviewer.strip(),review_note=note.strip())
    learning.setdefault('events',[]).append({'id':f"knowledge-review-{candidate_id}-{row['revision']}",
        'kind':'knowledge_review','candidate_id':candidate_id,'before':before,'after':target,
        'reviewed_by':reviewer.strip(),'note':note.strip(),'revision':row['revision']})
    learning['revision']=learning.get('revision',0)+1
    return row
