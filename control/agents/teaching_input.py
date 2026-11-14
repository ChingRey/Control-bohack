"""Compact project-chat inputs and evidence-linked continuity, without extra LLM calls."""
import copy
import json
import re
from . import checkpoints, coding_workflow, knowledge, memory

SOURCE_BUDGET = 6500

def content_note(note):
    # Workflow/acceptance facts come from the backend, never from model memory.
    return not re.search(r'✓|✕|已执行|未执行|待验收|验收通过|检查通过|不会自动', note.get('text',''))

def build(task, action):
    source = task.get('files', {})
    event = checkpoints.view(task, source)
    review = action in ('checkpoint', 'review')
    selected = {}
    evidence = (event or {}).get('project_evidence', {})
    changes = evidence.get('changes', [])
    # Send current source around actual diff hunks, not each file's first 120 lines.
    # The diff itself stays in storage, so inserted source is not sent twice.
    previous_hash=task.get('teaching',{}).get('continuity',{}).get('code_hash')
    changed_since_last_read=previous_hash!=knowledge.code_hash(source)
    if review and (changed_since_last_read or action=='review') and not evidence.get('stale_for_code'):
        per_file_budget = max(800, SOURCE_BUDGET // max(1, sum(c['file'] in source for c in changes)))
        for change in changes:
            name = change['file']
            if name not in source:
                continue
            lines = source[name].splitlines()
            wanted = set()
            for match in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', change.get('diff', ''), re.M):
                start = int(match[1]); count = int(match[2] or 1)
                wanted.update(range(max(1, start - 10), min(len(lines), start + max(count, 1) + 9) + 1))
            if not wanted and change.get('before_hash') is None:
                wanted.update(range(1, min(60,len(lines))+1))
            for number in sorted(wanted):
                row = {'line': number, 'text': lines[number - 1]}
                candidate = copy.deepcopy(selected)
                candidate.setdefault(name, []).append(row)
                if memory.size(candidate) > SOURCE_BUDGET or memory.size(candidate[name]) > per_file_budget:
                    break
                selected = candidate
    compact_event = None
    if event:
        compact_event = {k: event[k] for k in ('checkpoint_id', 'stage_index', 'kind')}
        compact_event['project_evidence'] = {
            'changes': [{'file': x['file'], 'deleted': x['file'] not in source,
                         'new_file': x.get('before_hash') is None,
                         'diff_truncated': x.get('diff_truncated', False),
                         'removed_lines': '\n'.join(line[1:] for line in x.get('diff', '').splitlines()
                             if line.startswith('-') and not line.startswith('---'))[:500]}
                        for x in changes],
            'stale_for_code': evidence.get('stale_for_code', False),
            'test_status': evidence.get('test_status', 'not_run'),
            'execution_records': evidence.get('execution_records', [])[-2:],
            'test_records': evidence.get('test_records', [])[-2:],
            'runtime_observations': evidence.get('runtime_observations', [])[-3:],
            'binary_changes': evidence.get('binary_changes', [])[:10],
            'notice': '执行记录和浏览器观察未经独立验证；源代码是快照，省略部分可按行读取。'}
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
    ctx = {'action': action, 'interaction_mode': 'project_chat',
           'code_changed_since_last_reply':changed_since_last_read,
           'current_request': {'message_id':focus} if action=='message' else
                              {'instruction':'检查本轮检查点；历史对话仅供接续，不重新回答旧问题。'},
           'development_scope': coding_workflow.phase_contract(task),
           'checkpoint_event': compact_event if review else None,
           'files': selected,
           'project_files': {'files': [{'path': n, 'line_count': len(v.splitlines())} for n,v in list(source.items())[:100]],
                             'total_file_count': len(source), 'omitted_file_count': max(0, len(source)-100),
                             'read_tool': 'read_project_file',
                             'notice': '仅预载本轮变更附近源码。未显示不等于不存在；可按路径和行号只读补查。'},
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
                            'input_revision': 'compact-v1', 'source_budget_characters': SOURCE_BUDGET}
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
