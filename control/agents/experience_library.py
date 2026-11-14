"""Single-demo-user playbook, shared across projects. SQLite CAS and reversible deltas."""
import copy
import json
import time
import uuid
from . import teaching_evolution as evolution

SHARED = ('entries', 'revision', 'versions', 'reviews', 'mode', 'auto', 'batches', 'preset_versions')


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def read(c):
    c.execute('CREATE TABLE IF NOT EXISTS experience_library (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')
    row = c.execute('SELECT body FROM experience_library WHERE id=1').fetchone()
    if row:
        book=json.loads(row[0])
        book.setdefault('preset_versions',[])
        return install_presets(c,book)
    initial = evolution.state({})
    book = {k: copy.deepcopy(initial[k]) for k in SHARED if k in initial}
    book.update(mode='adaptive', auto=True, batches=[], scope='shared-demo')
    # Preserve historical project entries without inventing cross-project evidence.
    known = {e['id'] for e in book['entries']}
    for raw, in c.execute('SELECT body FROM tasks ORDER BY rowid'):
        task = json.loads(raw)
        for entry in task.get('teaching_evolution', {}).get('entries', []):
            if entry['id'] in known or entry.get('origin') == 'seed':
                continue
            imported = copy.deepcopy(entry)
            imported.update(source_project=task['id'], source_title=task.get('title', '历史项目'))
            book['entries'].append(imported)
            known.add(entry['id'])
    book.setdefault('preset_versions',[])
    write(c, book)
    return install_presets(c,book)


def write(c, book):
    c.execute('INSERT OR REPLACE INTO experience_library VALUES (1,?)', (encode(book),))


def install_presets(c, book):
    catalog=evolution.asset('presets-from-code-v1.json')
    version=catalog['version']
    if version in book.get('preset_versions',[]):return book
    before=copy.deepcopy(book['entries']);by_id={entry['id']:entry for entry in book['entries']}
    skipped=[]
    for row in catalog['entries']:
        if row['id'] in by_id:
            existing=by_id[row['id']]
            if existing.get('origin')!='seed':continue
            # Enrich provenance/verification design, never replace an edited
            # strategy or revive an inactive entry with the same catalog ID.
            fields={key:copy.deepcopy(row[key]) for key in ('rationale','example','source_refs','evidence_plan') if key not in existing}
            if fields:
                evolution.archive_entry(existing)
                existing.update(fields)
            continue
        if len(book['entries'])>=evolution.MAX_ENTRIES:
            skipped.append(row['id']);continue
        entry={**copy.deepcopy(row),'revision':1,'status':'trial','origin':'preset',
               'explicit_project_trial':True,'source_title':'代码预设策略','helpful':0,'harmful':0,
               'uncertain':0,'evidence_ids':[],'verified':False,'history':[]}
        book['entries'].append(entry)
    # A catalog installation is an auditable/reversible batch. The installation
    # marker is preserved on undo/restore, so future GETs cannot resurrect it.
    book['preset_versions']=list(dict.fromkeys(book.get('preset_versions',[])+[version]))
    changes=delta(before,book['entries'])
    if changes:
        book['versions'].append({'revision':book['revision'],'reason':'整理已有代码预设教法','entries':before})
        previous=book['revision'];book['revision']+=1
        book['batches'].append({'id':uuid.uuid4().hex,'kind':'preset_import','catalog_version':version,
           'created_at':time.time(),'project_title':'已有代码中的预设教法','before_revision':previous,
           'after_revision':book['revision'],'reason':'结构化整理，不代表经过学生效果验证。',
           'changes':changes,'capacity_skipped':skipped})
    write(c,book)
    return book


def trial_observations(c, book):
    """Operational exposure/feedback, not proof that a teaching action happened."""
    stats = {entry['id']: {'entry_revision':entry['revision'], 'provided_count':0,
                          'helpful':0,'harmful':0,'uncertain':0,'stage':'pending'}
             for entry in book['entries'] if entry['status']=='trial'}
    seen=set()
    for raw, in c.execute('SELECT body FROM tasks'):
        task=json.loads(raw)
        for load in task.get('teaching_evolution',{}).get('loads',[]):
            for entry in load.get('entries',[]):
                stat=stats.get(entry['id'])
                key=(task['id'],load['reply_message_id'],entry['id'],entry['revision'])
                if stat and stat['entry_revision']==entry['revision'] and key not in seen:
                    stat['provided_count']+=1;seen.add(key)
    for review in book['reviews']:
        for feedback in review.get('evaluation',{}).get('feedback',[]):
            stat=stats.get(feedback['entry_id'])
            if stat and stat['entry_revision']==feedback['entry_revision']:
                stat[feedback['outcome']]+=1
    for stat in stats.values():
        if stat['harmful']:stat['stage']='negative_observation'
        elif stat['helpful']:stat['stage']='positive_observation'
        elif stat['uncertain']:stat['stage']='inconclusive'
        elif stat['provided_count']:stat['stage']='awaiting_evidence'
    return stats


def attach(c, task):
    book = read(c)
    local = evolution.state(task)
    for key in SHARED:
        local[key] = copy.deepcopy(book[key]) if key != 'reviews' else [copy.deepcopy(r) for r in book[key] if r.get('source_project')==task.get('id')]
    local['trial_observations']=trial_observations(c,book)
    local['scope'] = 'shared-demo'
    return local


def view(c):
    book = read(c)
    runs = []
    uses = []
    project_names = {}
    for raw, in c.execute('SELECT body FROM tasks'):
        task = json.loads(raw)
        project_names[task['id']]=task.get('title','未命名仓库')
        for load in task.get('teaching_evolution',{}).get('loads',[])[-20:]:
            reply_id=load['reply_message_id']
            message=task.get('messages',[])[reply_id] if 0<=reply_id<len(task.get('messages',[])) else {}
            uses.append({**copy.deepcopy(load),'project_id':task['id'],'project_title':task.get('title'),'reply':message.get('content','')})
        run = task.get('teaching_evolution', {}).get('run', {})
        if run.get('id'):
            runs.append({'project_id': task['id'], 'title': task.get('title'), 'run': run})
    return {**book, 'project_names':project_names,'project_runs': runs, 'uses': uses[-100:], 'trial_observations':trial_observations(c,book)}


def delta(before, after):
    old = {e['id']: e for e in before}
    new = {e['id']: e for e in after}
    return [{'entry_id': key, 'before': copy.deepcopy(old.get(key)), 'after': copy.deepcopy(new.get(key))}
            for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)]


def commit_review(c, task, review, result):
    # Caller holds a BEGIN IMMEDIATE transaction. Projects cannot overwrite one
    # another's revisions even if their model responses finish simultaneously.
    attach(c, task)
    state = evolution.state(task)
    before = copy.deepcopy(state['entries'])
    evolution.apply(task, review, result)
    state = evolution.state(task)
    for entry in state['entries']:
        if entry['id'] not in {e['id'] for e in before}:
            entry.update(status='trial', explicit_project_trial=True,
                         source_project=task['id'], source_title=task.get('title', '项目'))
    state['reviews'][-1]['source_project']=task['id']
    batch = {'id': uuid.uuid4().hex, 'kind': 'reflection', 'created_at': time.time(),
             'project_id': task['id'], 'project_title': task.get('title', '项目'),
             'before_revision': review['playbook_revision'], 'after_revision': state['revision'],
             'review': copy.deepcopy(state['reviews'][-1]),
             'evidence_messages': copy.deepcopy(review['messages']), 'evidence':copy.deepcopy(review.get('evidence',[])),
             'changes': delta(before, state['entries'])}
    state['batches'].append(batch)
    book = {k: copy.deepcopy(state[k]) for k in SHARED}
    book['scope'] = 'shared-demo'
    previous=read(c)
    book['reviews']=previous['reviews']+[copy.deepcopy(state['reviews'][-1])]
    write(c, book)
    return batch


def manage(c, body):
    book = read(c)
    if type(body.get('expected_revision')) is not int or body['expected_revision'] != book['revision']:
        raise ValueError('经验库已更新，请刷新后操作')
    task = {'teaching_evolution': {**copy.deepcopy(book), 'cursor': -1, 'deferred_ids': [], 'loads': [], 'run': {'status': 'idle'}}}
    state = task['teaching_evolution']
    before = copy.deepcopy(book['entries'])
    action = body.get('action')
    if action == 'undo':
        batch = next((b for b in state['batches'] if b['id'] == body.get('batch_id')), None)
        if not batch:
            raise ValueError('本轮变更不存在')
        changes = [d for d in batch['changes'] if not d.get('undone') and
                   (not body.get('entry_id') or d['entry_id'] == body['entry_id'])]
        if not changes:
            raise ValueError('没有可以撤销的变更')
        entries = {e['id']: e for e in state['entries']}
        for change in changes:
            if entries.get(change['entry_id']) != change['after']:
                raise ValueError('这条经验后来又有变化，请先撤销较新的变更，避免覆盖')
        evolution.checkpoint(state, '撤销本轮经验变更')
        for change in changes:
            current = entries[change['entry_id']]
            history = copy.deepcopy(current.get('history', [])) + [{k: copy.deepcopy(v) for k,v in current.items() if k != 'history'}]
            restored = copy.deepcopy(change['before'] or current)
            if change['before'] is None:
                restored['status'] = 'inactive'
                restored['explicit_project_trial'] = False
            restored.update(revision=current['revision']+1, history=history)
            state['entries'][state['entries'].index(current)] = restored
            change['undone'] = True
        # Undo controls subsequent inputs, not messages, scores or evidence cursors.
    else:
        if action == 'status' and body.get('status') == 'active':
            # This UI deliberately offers trial rather than claiming validation.
            body = {**body, 'status': 'trial'}
        evolution.manage(task, body)
        state = task['teaching_evolution']
    if action != 'undo':
        state['batches'].append({'id': uuid.uuid4().hex, 'kind': action, 'created_at': time.time(),
            'project_title': '经验库管理', 'before_revision': book['revision'], 'after_revision': state['revision'],
            'changes': delta(before, state['entries'])})
    result = {k: copy.deepcopy(state[k]) for k in SHARED}
    result['scope'] = 'shared-demo'
    write(c, result)
    return result
