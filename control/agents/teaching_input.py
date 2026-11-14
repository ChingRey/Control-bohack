"""Compact project-chat inputs and evidence-linked continuity, without extra LLM calls."""
import copy
import json
import re
from . import checkpoints, coding_workflow, knowledge, memory

SOURCE_BUDGET = 3600
MAX_FUTURE_STEPS = 3


def compact_shared(value):
    """Keep both draft and confirmed semantics without sending identical text twice."""
    value = copy.deepcopy(value)
    for name, rows in value.get('materials', {}).items():
        confirmed = value.get('confirmed_materials', {}).get(name)
        if confirmed and rows and rows[-1] == confirmed:
            value['materials'][name] = [{'same_as_confirmed': True, 'revision': confirmed['revision']}]
    return value

def content_note(note):
    # Workflow/acceptance facts come from the backend, never from model memory.
    return not re.search(r'✓|✕|已执行|未执行|待验收|验收通过|检查通过|不会自动', note.get('text',''))

def compact_scope(task):
    scope=coding_workflow.phase_contract(task)
    future=scope.get('future',[])
    return {**{key:scope[key] for key in (
        'plan_confirmed','current_index','current_title','requires_file_change',
        'execution_status','acceptance_status','execution_mode','current_status','boundary')},
        'future':future[:MAX_FUTURE_STEPS],
        'future_omitted_count':max(0,len(future)-MAX_FUTURE_STEPS)}


def focused_source(task, question, changes):
    """Select complete current lines locally; deleted lines stay in checkpoint evidence."""
    source = task.get('files', {})
    ranked = {}
    explicit = set()
    def add(name, number, priority, radius=3):
        lines = source[name].splitlines()
        for n in range(max(1, number-radius), min(len(lines), number+radius)+1):
            score = priority if n == number else priority-20-abs(n-number)
            ranked[(name,n)] = max(score, ranked.get((name,n), -1))
    for name, body in source.items():
        match = re.search(r'(?<![\w/.-])'+re.escape(name)+r'(?![\w/.-])(?::(\d+)(?:-(\d+))?)?', question)
        if match:
            explicit.add(name)
            if match[1]:
                start=int(match[1]);end=min(int(match[2] or start),start+60)
                for n in range(start,end+1):add(name,n,120)
            else:
                for n in range(1,min(24,len(body.splitlines()))+1):add(name,n,45,0)
    for change in changes:
        name=change.get('file')
        if name not in source:continue
        current=None;found=False
        for line in change.get('diff','').splitlines():
            hunk=re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)',line)
            if hunk:current=int(hunk[1]);add(name,current,80);continue
            if current is None:continue
            if line.startswith('+') and not line.startswith('+++'):
                add(name,current,100);current+=1;found=True
            elif line.startswith(' '):current+=1
            elif line.startswith('-') and not line.startswith('---'):add(name,current,90)
        if not found and change.get('before_hash') is None:
            for n in range(1,min(24,len(source[name].splitlines()))+1):add(name,n,50,0)
    terms=set(re.findall(r'[A-Za-z_$][A-Za-z0-9_$]{2,}',question))
    for name,body in source.items():
        hits=0
        for n,line in enumerate(body.splitlines(),1):
            if terms.intersection(re.findall(r'[A-Za-z_$][A-Za-z0-9_$]{2,}',line)):
                add(name,n,110 if name in explicit else 65,2);hits+=1
                if hits>=12:break
    selected={}
    for (name,n),score in sorted(ranked.items(),key=lambda x:(-x[1],x[0][0],x[0][1])):
        if name not in selected and len(selected)>=6:continue
        candidate=copy.deepcopy(selected)
        candidate.setdefault(name,[]).append({'line':n,'text':source[name].splitlines()[n-1]})
        if memory.size(candidate)>SOURCE_BUDGET or memory.size(candidate[name])>1800:continue
        selected=candidate
    for rows in selected.values():rows.sort(key=lambda r:r['line'])
    return selected

def build(task, action):
    source = task.get('files', {})
    event = checkpoints.view(task, source)
    review = action in ('checkpoint', 'review')
    selected = {}
    evidence = (event or {}).get('project_evidence', {})
    changes = evidence.get('changes', [])
    previous_hash=task.get('teaching',{}).get('continuity',{}).get('code_hash')
    changed_since_last_read=previous_hash!=knowledge.code_hash(source)
    compact_event = None
    if event:
        compact_event = {k: event[k] for k in ('checkpoint_id', 'stage_index', 'kind')}
        compact_changes=changes[:8]
        compact_event['project_evidence'] = {
            'changes': [{'file': x['file'], 'deleted': x['file'] not in source,
                         'new_file': x.get('before_hash') is None,
                         'diff_truncated': x.get('diff_truncated', False),
                         'removed_lines': '\n'.join(line[1:] for line in x.get('diff', '').splitlines()
                             if line.startswith('-') and not line.startswith('---'))[:240]}
                        for x in compact_changes],
            'omitted_change_count':max(0,len(changes)-len(compact_changes)),
            'stale_for_code': evidence.get('stale_for_code', False),
            'test_status': evidence.get('test_status', 'not_run'),
            'execution_records': evidence.get('execution_records', [])[-1:],
            'test_records': evidence.get('test_records', [])[-1:],
            'runtime_observations': evidence.get('runtime_observations', [])[-2:],
            'binary_changes': evidence.get('binary_changes', [])[:5],
            'notice': '执行记录和浏览器观察未经独立验证；源码仅为重点片段，省略部分不作为判断依据。'}
    history = task['messages']
    eligible = [i for i,m in enumerate(history) if m.get('queue_status') not in ('queued','needs_retry')]
    focus = next((i for i in range(len(history)-1, -1, -1) if i in eligible and history[i]['role'] == 'user' and
                  history[i]['channel'] == ('teaching' if action == 'message' else 'coding')), None)
    # Keep a small tail and the current question verbatim; drop transport/UI metadata.
    ids = set(eligible[-4:])
    if review:
        ids = set([i for i,m in enumerate(history) if i in eligible and m['channel']=='coding'][-3:])
        prior = next((i for i in range(len(history)-1,-1,-1) if i in eligible and history[i]['channel']=='teaching' and history[i]['role']=='assistant'),None)
        if prior is not None:ids.add(prior)
    initial = next((i for i,m in enumerate(history) if i in eligible and m['channel']=='coding' and m['role']=='user'), None)
    if initial is not None:
        ids.add(initial)
    if focus is not None:
        ids.add(focus)
    question = history[focus]['content'] if focus is not None else ''
    needs_code = review or bool(re.search(r'代码|源码|修改|改动|报错|函数|变量|bug|error', question, re.I))
    selected = focused_source(task, question, changes if needs_code and not evidence.get('stale_for_code') else [])
    messages = []
    seen = set()
    for i in sorted(ids):
        item = history[i]
        key = (item['channel'], item['role'], item['content'])
        if key in seen:
            continue
        seen.add(key)
        limit = len(item['content']) if i == focus else 600 if i==initial else 700
        messages.append({'id': i, 'channel': item['channel'], 'role': item['role'],
                         'content': item['content'][:limit], 'truncated': len(item['content']) > limit})
    relevant_files=[{'path':name,'line_count':len(source[name].splitlines()),
                     'preloaded_lines':[row['line'] for row in rows]}
                    for name,rows in selected.items() if name in source]
    scope=compact_scope(task)
    ctx = {'action': action, 'interaction_mode': 'project_chat',
           'code_changed_since_last_reply':changed_since_last_read,
           'current_request': {'message_id':focus} if action=='message' else
                              {'instruction':'根据当前教学阶段和接续记忆继续教学；本轮检查点是作品材料，不是要求只做代码审查。历史问题不重复回答。'},
           'development_scope': scope,
           'checkpoint_event': compact_event if review else None,
           'files': selected,
           'project_files': {'files': [{'path':n,'line_count':len(v.splitlines())} for n,v in list(source.items())[:100]],
                             'relevant_files':relevant_files,
                             'omitted_file_count':max(0,len(source)-100),
                             'total_file_count': len(source),
                             'selection_mode': 'local_focus_and_diff',
                             'notice': '仅提供本轮重点源码和修改行附近的完整行；省略部分不代表不存在。本轮不调用读取工具，证据不足时说明缺少什么，不猜测源码或行号。'},
           'code_hash': knowledge.code_hash(source),
           'messages': messages,
           'student_evidence': [{'id': m['id']} for m in messages if m['role'] == 'user'],
           'continuity_memory': copy.deepcopy(task.get('teaching', {}).get('continuity', {})),
           'loaded_skills': {}}
    if ctx['continuity_memory'].get('notes'):
        ctx['continuity_memory']['notes']=[n for n in ctx['continuity_memory']['notes'] if content_note(n)]
    ctx['continuity_memory']['stale_for_code'] = bool(ctx['continuity_memory'].get('code_hash') and
                                                    ctx['continuity_memory']['code_hash'] != ctx['code_hash'])
    ctx['continuity_memory']['notes_stale_for_code'] = bool(ctx['continuity_memory'].get('notes_code_hash') and
                                                          ctx['continuity_memory']['notes_code_hash'] != ctx['code_hash'])
    if not ctx['continuity_memory'].get('revision'):
        legacy = task.get('teaching', {}).get('memory', {})
        segments = legacy.get('segments', [])[-1:]
        ctx['continuity_memory']['legacy_notes'] = [{'from_id':s['from_id'],'to_id':s['to_id'],
                                                   'summary':s['summary'][:600]} for s in segments]
    if memory.size(ctx) > memory.MAX_CONTEXT_CHARS:
        raise ValueError('本轮教学材料超过80000个JSON字符，请缩小问题范围；原始记录已保留')
    ctx['context_usage'] = {'json_characters': memory.size(ctx), 'limit_characters': memory.MAX_CONTEXT_CHARS,
                            'counter': 'characters_not_tokens', 'loaded_message_ids': [m['id'] for m in messages],
                            'input_revision': 'single-pass-focus-v2', 'source_budget_characters': SOURCE_BUDGET}
    return ctx


def split_reply(text, ctx):
    """Hidden trailing notes are optional. Invalid notes never replace prior memory."""
    match = re.search(r'<continuity_memory>(.*?)</continuity_memory>\s*$', text, re.S)
    if not match:
        # Hide incomplete memory markers, but keep the natural response usable.
        return text.split('<continuity_memory>', 1)[0].strip(), None
    reply = text[:match.start()].strip()
    try:
        obj = json.loads(match[1]); notes = obj['notes']
        allowed = set(ctx['context_usage']['loaded_message_ids'])
        for note in ctx.get('continuity_memory',{}).get('notes',[]):
            allowed.update(note.get('evidence_ids',[]))
        if not isinstance(notes, list) or not 1 <= len(notes) <= 5:
            return reply, None
        for note in notes:
            if set(note) != {'kind', 'text', 'evidence_ids'} or note['kind'] not in ('discussed', 'student_decision', 'open_question', 'next_step'):
                return reply, None
            if not isinstance(note['text'], str) or not 1 <= len(note['text']) <= 240:
                return reply, None
            ids = note['evidence_ids']
            if not isinstance(ids, list) or not ids or len(ids)>6 or any(type(i) is not int or i not in allowed for i in ids):
                return reply, None
        return reply, [n for n in notes if content_note(n)] or None
    except (ValueError, KeyError, TypeError):
        return reply, None


def remember(task, ctx, reply, notes):
    rows = ctx['messages']
    # Exact excerpts remain useful if the model omitted or malformed its notes.
    last_user = next((m for m in reversed(rows) if m['role'] == 'user'), None)
    old = task.get('teaching', {}).get('continuity', {})
    task['teaching']['continuity'] = {
        'revision': old.get('revision', 0)+1, 'kind': 'model_notes_not_verified_mastery',
        'notes': notes if notes is not None else old.get('notes', []),
        'notes_code_hash': ctx['code_hash'] if notes is not None else old.get('notes_code_hash'),
        'last_exchange': {'student': last_user['content'][:350] if last_user else '',
                          'student_message_id': last_user['id'] if last_user else None,
                          'teacher_reply_excerpt': reply[:500], 'teacher_reply_truncated': len(reply)>500},
        'source_message_ids': sorted(set(i for note in notes for i in note['evidence_ids'])) if notes is not None else old.get('source_message_ids',[]),
        'code_hash': ctx['code_hash'],
        'notice': '接续笔记可能有误；来源编号可查原话。不是掌握证明，不代替最新计划、执行或验收状态。'}
